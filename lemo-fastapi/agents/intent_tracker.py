"""IntentTracker — the first node in the LangGraph pipeline.

Responsibilities:
    1. Pull the last 10 chat turns + any cached intent from Redis.
    2. Ask `gemini-3.1-flash` (structured output) to classify scope + next_action.
    3. Cache the result for ~1h so repeated queries are cheap.
    4. Fall back to the legacy keyword heuristic on any failure so the graph
       never stalls on an LLM outage.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Literal, Optional

from pydantic import BaseModel, Field

from agents.state import LemoState
from helpers import gemini_client
from helpers.intent_detection import fallback_intent_detection
from helpers.llm_config import (
    LLMConfigurationError,
    LLMServiceUnavailableError,
    normalize_llm_exception,
)
from prompts.intent_detection_v2 import (
    build_intent_user_message,
    intent_detection_prompt_v2,
)

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 60 * 60  # 1 hour


class IntentOutputV2(BaseModel):
    """Structured output schema handed to Gemini's response_schema."""

    intent: Literal["ask", "todo", "unknown"] = Field(description="Intent type")
    scope: Literal[
        "current_page",
        "product",
        "chat_history",
        "cart",
        "order",
        "wishlist",
        "account",
        "unknown",
    ] = Field(description="Scope of the intent")
    next_action: Literal[
        "answer_from_history",
        "scrape_current_page",
        "discover_and_compare",
        "chat_history_summary",
        "direct_answer",
    ] = Field(description="Next action in the pipeline")
    query_for_scraper: str = Field(
        default="",
        description="Clean search string for Google SERP; empty if not needed",
    )
    intent_reasoning: str = Field(default="", description="One-sentence rationale")


# ---------------------------------------------------------------------------
# Redis cache helpers
# ---------------------------------------------------------------------------


def _cache_key(session_id: str, user_query: str) -> str:
    digest = hashlib.md5(user_query.strip().lower().encode("utf-8")).hexdigest()
    return f"intent:cache:{session_id}:{digest}"


async def _load_cached_intent(session_id: str, user_query: str) -> Optional[dict]:
    try:
        from helpers.redis_functions import get_redis_connection

        r = await get_redis_connection()
        try:
            raw = await r.get(_cache_key(session_id, user_query))
        finally:
            await r.close()
        if not raw:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return json.loads(raw)
    except Exception as exc:
        logger.debug("[agent=intent] cache read skipped: %s", exc)
        return None


async def _store_cached_intent(session_id: str, user_query: str, value: dict) -> None:
    try:
        from helpers.redis_functions import get_redis_connection

        r = await get_redis_connection()
        try:
            await r.setex(
                _cache_key(session_id, user_query),
                _CACHE_TTL_SECONDS,
                json.dumps(value),
            )
        finally:
            await r.close()
    except Exception as exc:
        logger.debug("[agent=intent] cache write skipped: %s", exc)


# ---------------------------------------------------------------------------
# Main node
# ---------------------------------------------------------------------------


def _format_history(history: list[dict]) -> list[str]:
    lines: list[str] = []
    for msg in history[-10:]:
        role = msg.get("message_type") or "user"
        text = (msg.get("message") or "").strip().replace("\n", " ")
        if not text:
            continue
        lines.append(f"{role}: {text[:500]}")
    return lines


def _heuristic_next_action(scope: str, user_query: str) -> str:
    q = (user_query or "").lower()
    if scope == "chat_history":
        return "chat_history_summary"
    if scope == "product" or any(
        tok in q for tok in ("compare", "flipkart", "amazon", "cheaper", "alternative", "similar")
    ):
        return "discover_and_compare"
    if scope == "current_page":
        return "scrape_current_page"
    return "direct_answer"


async def intent_tracker_node(state: LemoState) -> dict:
    """LangGraph node. Returns a partial state update."""
    user_query = state.get("user_query", "")
    session_id = state.get("session_id", "")
    current_url = state.get("current_page_url", "") or ""
    domain = state.get("domain", "") or ""
    chat_history = state.get("chat_history", []) or []

    logger.info(">>> [1/3] INTENT TRACKER (agent=intent, model=%s)", gemini_client.fast_model())
    t0 = time.perf_counter()

    cached = await _load_cached_intent(session_id, user_query) if session_id else None
    if cached:
        logger.info("    cache hit: %s", {k: cached.get(k) for k in ("intent", "scope", "next_action")})

    update: dict = {"cached_intent": cached}

    try:
        history_lines = _format_history(chat_history)
        user_message = build_intent_user_message(
            user_query=user_query,
            current_url=current_url,
            domain=domain,
            chat_history_lines=history_lines,
            cached_intent=cached,
        )

        logger.info("[agent=intent] Classifying query=%r", user_query[:120])

        result = await gemini_client.generate(
            user=user_message,
            model=gemini_client.fast_model(),
            system=intent_detection_prompt_v2,
            temperature=0.2,
            max_output_tokens=512,
            schema=IntentOutputV2,
        )

        if result is None:
            raise RuntimeError("Gemini returned no structured output")

        update.update(
            {
                "intent": result.intent,
                "scope": result.scope,
                "next_action": result.next_action,
                "query_for_scraper": (result.query_for_scraper or "").strip(),
                "intent_reasoning": result.intent_reasoning or "",
            }
        )

        # Cache the decision for 1h
        if session_id:
            await _store_cached_intent(
                session_id,
                user_query,
                {
                    "intent": result.intent,
                    "scope": result.scope,
                    "next_action": result.next_action,
                    "query_for_scraper": result.query_for_scraper,
                },
            )

        logger.info(
            "<<< [1/3] INTENT done in %.0fms -> intent=%s scope=%s next_action=%s q_for_scraper=%r",
            (time.perf_counter() - t0) * 1000,
            result.intent,
            result.scope,
            result.next_action,
            (result.query_for_scraper or "")[:80],
        )
        return update

    except Exception as exc:
        normalized = normalize_llm_exception(exc)
        if isinstance(normalized, (LLMConfigurationError, LLMServiceUnavailableError)):
            logger.warning("[agent=intent] LLM unavailable, using heuristic: %s", normalized)
        else:
            logger.warning("[agent=intent] classification failed, using heuristic: %s", exc)

        fb = fallback_intent_detection(user_query)
        next_action = _heuristic_next_action(fb.scope, user_query)
        errors = list(state.get("errors") or [])
        errors.append(f"intent_tracker: {normalized}")
        update.update(
            {
                "intent": fb.intent,
                "scope": fb.scope,
                "next_action": next_action,
                "query_for_scraper": "",
                "intent_reasoning": "heuristic fallback",
                "errors": errors,
            }
        )
        logger.info(
            "<<< [1/3] INTENT (heuristic) done in %.0fms -> intent=%s scope=%s next_action=%s",
            (time.perf_counter() - t0) * 1000,
            fb.intent,
            fb.scope,
            next_action,
        )
        return update


def route_after_intent(state: LemoState) -> str:
    """Conditional edge: decide whether to call the Scraper or go straight to Lemo."""
    next_action = state.get("next_action", "direct_answer")
    if next_action in ("scrape_current_page", "discover_and_compare"):
        return "needs_scrape"
    return "direct_answer"
