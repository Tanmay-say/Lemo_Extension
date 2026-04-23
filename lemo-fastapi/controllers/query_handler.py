"""Entry point for POST /query."""

from __future__ import annotations

import hashlib
import logging
import time
from urllib.parse import urlparse

from fastapi import Request
from fastapi.responses import JSONResponse

from agents.graph import run_lemo_pipeline
from agents.state import LemoState
from dependencies.auth import get_optional_user
from helpers.add_chats import add_chats
from helpers.get_session_details import get_session_details
from helpers.llm_config import (
    LLMConfigurationError,
    LLMServiceUnavailableError,
    normalize_llm_exception,
    user_facing_llm_message,
)
from helpers.runtime_cache import get_json, set_json

logger = logging.getLogger(__name__)

ANSWER_CACHE_TTL_SECONDS = 10 * 60


def _derive_domain(url: str) -> str:
    try:
        netloc = urlparse(url).netloc.lower()
        return netloc.removeprefix("www.")
    except Exception:
        return ""


def _history_fingerprint(chat_history: list[dict]) -> str:
    if not chat_history:
        return "empty"
    last = chat_history[-1]
    parts = [
        str(len(chat_history)),
        str(last.get("message_type") or ""),
        str(last.get("message") or "")[:200],
        str(last.get("created_at") or ""),
    ]
    return hashlib.md5("|".join(parts).encode("utf-8")).hexdigest()


def _answer_cache_key(
    *,
    session_id: str,
    user_id: str,
    current_page_url: str,
    user_query: str,
    chat_history: list[dict],
) -> str:
    raw = "|".join(
        [
            session_id,
            user_id,
            current_page_url.strip().lower(),
            user_query.strip().lower(),
            _history_fingerprint(chat_history),
        ]
    )
    return f"answer:cache:{hashlib.md5(raw.encode('utf-8')).hexdigest()}"


async def _resolve_user_id(request: Request) -> str | None:
    auth_header = (request.headers.get("Authorization") or "").strip()
    if not auth_header:
        return None
    if not auth_header.startswith("Bearer "):
        return None
    user = await get_optional_user(request)
    return user.id if user else None


async def query_handler(request: Request):
    """Handle user queries through the LEMO pipeline."""
    try:
        session_id = request.query_params.get("session_id")
        body = await request.json()

        if not session_id:
            return JSONResponse(
                content={"success": False, "message": "Session ID is required"},
                status_code=400,
            )

        user_id = await _resolve_user_id(request)
        if not user_id:
            return JSONResponse(
                content={"success": False, "message": "User authentication required"},
                status_code=401,
            )

        user_query = (body.get("user_query") or "").strip()
        if not user_query:
            return JSONResponse(
                content={"success": False, "message": "User query is required"},
                status_code=400,
            )

        session_details = await get_session_details(session_id, user_id)
        current_page_url = session_details.get("current_url")
        domain = session_details.get("current_domain") or _derive_domain(current_page_url or "")
        chat_history = session_details.get("chat_messages") or []

        if not current_page_url:
            return JSONResponse(
                content={"success": False, "message": "Current page URL not found in session"},
                status_code=400,
            )

        answer_cache_key = _answer_cache_key(
            session_id=session_id,
            user_id=user_id,
            current_page_url=current_page_url,
            user_query=user_query,
            chat_history=chat_history,
        )
        cached_response = await get_json(answer_cache_key)
        if isinstance(cached_response, dict) and cached_response.get("success") is True:
            logger.info("[query] answer cache hit for session=%s", session_id)
            return JSONResponse(content=cached_response, status_code=200)

        initial_state: LemoState = {
            "user_query": user_query,
            "session_id": session_id,
            "user_id": user_id,
            "domain": domain,
            "current_page_url": current_page_url,
            "chat_history": chat_history,
        }

        logger.info("QUERY session=%s user=%s domain=%s history=%d", session_id, user_id, domain, len(chat_history))

        t0 = time.perf_counter()
        result = await run_lemo_pipeline(initial_state)
        pipeline_ms = (time.perf_counter() - t0) * 1000

        answer = (result.get("final_answer") or "").strip() or "I couldn't generate a response. Please try again."
        intent_label = result.get("intent") or "ask"
        scraped_count = len(result.get("scraped_data") or [])
        errors = result.get("errors") or []

        logger.info(
            "PIPELINE RESULT %.0fms intent=%s scope=%s next_action=%s scraped=%d errors=%s",
            pipeline_ms,
            result.get("intent"),
            result.get("scope"),
            result.get("next_action"),
            scraped_count,
            errors if errors else "(none)",
        )

        await add_chats(session_id, user_query, "user", intent_label, user_id)
        if answer:
            await add_chats(session_id, answer, "assistant", intent_label, user_id)

        response_body: dict = {"success": True, "answer": answer}
        for key in ("product", "comparison", "ui"):
            value = result.get(key)
            if value is not None:
                response_body[key] = value
        if result.get("scope"):
            response_body["scope"] = result["scope"]
        if result.get("next_action"):
            response_body["next_action"] = result["next_action"]

        await set_json(answer_cache_key, response_body, ANSWER_CACHE_TTL_SECONDS)
        return JSONResponse(content=response_body, status_code=200)

    except ValueError as e:
        logger.error("ValueError in query_handler: %s", e)
        return JSONResponse(
            content={"success": False, "message": "Invalid request data"},
            status_code=400,
        )
    except (LLMConfigurationError, LLMServiceUnavailableError) as e:
        logger.error("LLM error in query_handler: %s", e)
        status_code = 503 if isinstance(e, LLMServiceUnavailableError) else 500
        return JSONResponse(
            content={"success": False, "message": user_facing_llm_message(e)},
            status_code=status_code,
        )
    except Exception as e:
        normalized = normalize_llm_exception(e)
        if isinstance(normalized, (LLMConfigurationError, LLMServiceUnavailableError)):
            logger.error("Normalized LLM error in query_handler: %s", normalized)
            status_code = 503 if isinstance(normalized, LLMServiceUnavailableError) else 500
            return JSONResponse(
                content={"success": False, "message": user_facing_llm_message(normalized)},
                status_code=status_code,
            )
        logger.error("Unexpected error in query_handler: %s", e, exc_info=True)
        return JSONResponse(
            content={"success": False, "message": "An error occurred processing your request"},
            status_code=500,
        )
