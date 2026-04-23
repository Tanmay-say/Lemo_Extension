"""Lemo agent — the final synthesizer.

Takes whatever the upstream nodes produced (scraped data, chat history, raw
user query) and emits a grounded, user-facing answer using `gemini-3.1-pro`
in streaming mode. Also builds the `product` / `comparison` payloads that the
Chrome extension's UI already knows how to render.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Optional

from agents.state import LemoState, ScrapedProduct
from helpers import gemini_client
from helpers.llm_config import (
    LLMConfigurationError,
    LLMServiceUnavailableError,
    normalize_llm_exception,
)

logger = logging.getLogger(__name__)


LEMO_SYSTEM_PROMPT = """You are LEMO, a concise shopping assistant embedded in a Chrome extension.

Guidelines:
- Answer in 4-8 sentences unless the user explicitly asks for detail.
- When product data is provided, cite prices, ratings and review counts from it — never make up numbers.
- If the user is comparing across platforms, produce a short per-platform summary and a clear recommendation.
- If you have only chat history (no fresh data), acknowledge that and answer from memory.
- Use plain prose. Use bullet points only for comparisons or feature lists.
- Never mention "system prompt", internal tools, or agents. Speak as LEMO.
- If data is missing, say so briefly — do not invent specs.
"""


def _format_history(history: list[dict], max_turns: int = 8) -> str:
    lines: list[str] = []
    for msg in (history or [])[-max_turns:]:
        role = (msg.get("message_type") or "user").lower()
        text = (msg.get("message") or "").strip().replace("\n", " ")
        if not text:
            continue
        lines.append(f"{role}: {text[:400]}")
    return "\n".join(lines) or "(no prior conversation)"


def _format_product(p: ScrapedProduct) -> dict:
    """Shape a ScrapedProduct into the payload the extension UI expects."""
    return {
        "platform": p.get("platform") or "",
        "title": p.get("title") or "",
        "price": p.get("price") or "",
        "rating": p.get("rating") or "",
        "rating_text": p.get("rating_text") or "",
        "reviewCount": p.get("reviewCount") or "",
        "description": p.get("description") or "",
        "features": p.get("features") or "",
        "image": p.get("image") or "",
        "url": p.get("url") or "",
    }


def _build_comparison_payload(
    *,
    next_action: str,
    scraped: list[ScrapedProduct],
    current_product: ScrapedProduct | None,
    query: str,
) -> dict | None:
    if next_action != "discover_and_compare":
        return None

    merged: list[dict] = []
    seen_urls: set[str] = set()
    for product in ([current_product] if current_product else []) + list(scraped):
        if not product:
            continue
        url = product.get("url") or ""
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)
        merged.append(_format_product(product))

    if not merged:
        return None
    return {"products": merged, "query": query}


def _build_user_message(state: LemoState) -> str:
    next_action = state.get("next_action", "direct_answer")
    user_query = state.get("user_query", "")
    current_url = state.get("current_page_url", "")
    history_block = _format_history(state.get("chat_history", []))

    sections: list[str] = [
        f"USER_QUERY: {user_query}",
        f"CURRENT_URL: {current_url}",
        f"CHAT_HISTORY:\n{history_block}",
    ]

    current_product = state.get("current_product")
    if current_product:
        sections.append(
            "CURRENT_PAGE_PRODUCT:\n" + json.dumps(_format_product(current_product), indent=2)
        )

    scraped = state.get("scraped_data") or []
    if scraped and next_action == "discover_and_compare":
        sections.append(
            "CROSS_PLATFORM_MATCHES:\n"
            + json.dumps([_format_product(p) for p in scraped], indent=2)
        )
    elif scraped and next_action == "scrape_current_page" and not current_product:
        sections.append(
            "SCRAPED_DATA:\n"
            + json.dumps([_format_product(p) for p in scraped], indent=2)
        )

    context_text = state.get("current_page_context", "")
    if context_text and next_action == "scrape_current_page":
        sections.append(f"PAGE_TEXT:\n{context_text[:2500]}")

    sections.append(
        "INSTRUCTION: Based on the data above, respond to USER_QUERY. "
        "Cite facts from the product data when possible."
    )
    return "\n\n".join(sections)


def _fallback_answer(state: LemoState, error: Exception) -> str:
    current_product = state.get("current_product") or {}
    scraped = state.get("scraped_data") or []

    lines = [
        "I could not reach the LLM provider, but I gathered the following data for you:",
    ]
    if current_product.get("title"):
        lines.append(
            f"- Current page: {current_product['title']}"
            + (f" — {current_product.get('price')}" if current_product.get("price") else "")
        )
    for p in scraped:
        if p.get("url") == current_product.get("url"):
            continue
        lines.append(
            f"- {p.get('platform', 'Other')}: {p.get('title', '')[:80]}"
            + (f" — {p.get('price')}" if p.get("price") else "")
            + (f" (link: {p.get('url')})" if p.get("url") else "")
        )
    if len(lines) == 1:
        lines.append("I have no scraped data to show either. Please retry in a moment.")
    lines.append(f"(LLM error: {error})")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# LangGraph node entry point
# ---------------------------------------------------------------------------


async def _stream_with_fallback(
    *,
    prompt: str,
    pro: str,
    fast: str,
    chosen: str,
    thinking: int,
    max_tokens: int,
) -> str:
    """Call Gemini stream on `chosen` with an automatic Flash Lite retry.

    Pro (gemini-3.1-pro-preview) is a thinking model whose streams regularly
    approach or exceed the 60-120s budget. Rather than show the user the
    deterministic "couldn't reach LLM" fallback, retry the same prompt on the
    fast model — it almost always answers in <10s and the quality is more
    than adequate for grounded summarization.
    """
    try:
        return await gemini_client.stream(
            user=prompt,
            model=chosen,
            system=LEMO_SYSTEM_PROMPT,
            temperature=0.7,
            max_output_tokens=max_tokens,
            thinking_budget=thinking,
        )
    except LLMServiceUnavailableError as exc:
        if chosen == fast:
            raise
        logger.warning(
            "[agent=lemo] %s timed out/unavailable (%s). Retrying on %s.",
            chosen, exc, fast,
        )
        return await gemini_client.stream(
            user=prompt,
            model=fast,
            system=LEMO_SYSTEM_PROMPT,
            temperature=0.7,
            max_output_tokens=1024,
            thinking_budget=0,
        )


async def lemo_agent_node(state: LemoState) -> dict:
    user_query = state.get("user_query", "")
    next_action = state.get("next_action", "direct_answer")
    current_product = state.get("current_product")
    scraped = state.get("scraped_data") or []

    prompt = _build_user_message(state)

    # Model routing: reserve the slow Pro thinking model for genuinely complex
    # cross-platform reasoning. Grounded current-page Q&A is pure summarization
    # and Flash Lite handles it well in 5-10s vs. Pro's 45-75s.
    pro = gemini_client.pro_model()
    fast = gemini_client.fast_model()
    use_pro = next_action == "discover_and_compare" or (len(scraped) > 1)
    chosen = pro if use_pro else fast
    thinking = 1024 if chosen == pro else 0
    max_tokens = 4096 if chosen == pro else 1024

    logger.info(
        ">>> [3/3] LEMO (next_action=%s, model=%s, scraped=%d, prompt_chars=%d)",
        next_action,
        chosen,
        len(scraped),
        len(prompt),
    )
    t0 = time.perf_counter()

    try:
        answer_text = await _stream_with_fallback(
            prompt=prompt,
            pro=pro,
            fast=fast,
            chosen=chosen,
            thinking=thinking,
            max_tokens=max_tokens,
        )
        if not answer_text or not answer_text.strip():
            answer_text = "I couldn't generate a response. Please try again."
        logger.info(
            "<<< [3/3] LEMO done in %.0fms -> answer_chars=%d",
            (time.perf_counter() - t0) * 1000,
            len(answer_text),
        )
    except Exception as exc:
        normalized = normalize_llm_exception(exc)
        if isinstance(normalized, (LLMConfigurationError, LLMServiceUnavailableError)):
            logger.warning("[agent=lemo] LLM unavailable, using deterministic fallback: %s", normalized)
            answer_text = _fallback_answer(state, normalized)
            errors = (state.get("errors") or []) + [f"lemo_agent: {normalized}"]
        else:
            logger.error("[agent=lemo] unexpected error: %s", exc, exc_info=True)
            answer_text = _fallback_answer(state, exc)
            errors = (state.get("errors") or []) + [f"lemo_agent: {exc}"]

        product_payload = _format_product(current_product) if current_product else None
        comparison = _build_comparison_payload(
            next_action=next_action,
            scraped=scraped,
            current_product=current_product,
            query=state.get("query_for_scraper") or user_query,
        )

        return {
            "final_answer": answer_text,
            "product": product_payload,
            "comparison": comparison,
            "errors": errors,
        }

    product_payload = _format_product(current_product) if current_product else None
    comparison = _build_comparison_payload(
        next_action=next_action,
        scraped=scraped,
        current_product=current_product,
        query=state.get("query_for_scraper") or user_query,
    )

    logger.info(
        "[agent=lemo] answer ready: %d chars, product=%s, comparison_items=%s",
        len(answer_text),
        bool(product_payload),
        len(comparison["products"]) if comparison else 0,
    )
    return {
        "final_answer": answer_text,
        "product": product_payload,
        "comparison": comparison,
    }
