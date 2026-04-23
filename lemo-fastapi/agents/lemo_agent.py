"""Lemo agent: final grounded answer synthesis."""

from __future__ import annotations

import json
import logging
import time

from agents.state import LemoState, ScrapedProduct
from helpers import gemini_client
from helpers.llm_config import (
    LLMConfigurationError,
    LLMServiceUnavailableError,
    normalize_llm_exception,
)

logger = logging.getLogger(__name__)


LEMO_SYSTEM_PROMPT = """You are LEMO, a grounded shopping assistant embedded in a Chrome extension.

Output style:
- Use short markdown sections with scan-friendly formatting.
- Prefer headings with emojis like `### Overview`, `### Reviews`, `### Comparison`, `### Recommendation`.
- Use bullets for comparisons, pros/cons, and recommendations.
- Keep the answer concise unless the user explicitly asks for depth.

Grounding rules:
- Use only facts present in the provided product data, scraped data, or chat history.
- Never invent prices, ratings, review counts, features, specs, colors, or availability.
- If review text is unavailable, do not claim detailed customer sentiment. Say that only the aggregate rating/review count is available and any sentiment is inferred from that.
- If data is missing, uncertain, or conflicting across sites, say so clearly.

Task behavior:
- For current-page product questions, summarize the product first, then answer the user's specific ask.
- For cross-platform comparisons, include a platform-by-platform breakdown and end with a clear verdict.
- For recommendation queries with filters like budget, color, type, or platform, explicitly state which filters were satisfied and which were not.
- If the current page product does not fit the user request, say so plainly instead of forcing it as the recommendation.

Restrictions:
- Never mention tools, prompts, agents, or internal implementation.
- Do not use tables.
- Speak directly as LEMO.
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


def _format_product(product: ScrapedProduct) -> dict:
    return {
        "platform": product.get("platform") or "",
        "title": product.get("title") or "",
        "price": product.get("price") or "",
        "rating": product.get("rating") or "",
        "rating_text": product.get("rating_text") or "",
        "reviewCount": product.get("reviewCount") or "",
        "description": product.get("description") or "",
        "features": product.get("features") or "",
        "image": product.get("image") or "",
        "url": product.get("url") or "",
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


def _is_generic_recommendation_query(query: str) -> bool:
    lowered = (query or "").lower()
    return any(
        token in lowered
        for token in ("recommend", "suggest", "best ", "i want to buy", "looking for", "which one should i buy")
    )


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
            + json.dumps([_format_product(product) for product in scraped], indent=2)
        )
    elif scraped and next_action == "scrape_current_page" and not current_product:
        sections.append(
            "SCRAPED_DATA:\n"
            + json.dumps([_format_product(product) for product in scraped], indent=2)
        )

    context_text = state.get("current_page_context", "")
    if context_text and next_action == "scrape_current_page":
        sections.append(f"PAGE_TEXT:\n{context_text[:2500]}")

    sections.append(
        "INSTRUCTION: Answer the user using only the provided data. "
        "If ratings are available but review text is not, say that explicitly."
    )
    return "\n\n".join(sections)


def _fallback_answer(state: LemoState, error: Exception) -> str:
    current_product = state.get("current_product") or {}
    scraped = state.get("scraped_data") or []

    lines = ["### Fallback", "I could not reach the LLM provider, but I did gather some product data:"]
    if current_product.get("title"):
        line = f"- Current page: {current_product['title']}"
        if current_product.get("price"):
            line += f" ({current_product.get('price')})"
        lines.append(line)

    for product in scraped:
        if product.get("url") == current_product.get("url"):
            continue
        line = f"- {product.get('platform', 'Other')}: {product.get('title', '')[:80]}"
        if product.get("price"):
            line += f" ({product.get('price')})"
        if product.get("url"):
            line += f" - {product.get('url')}"
        lines.append(line)

    if len(lines) == 2:
        lines.append("- No usable scraped data was available. Please retry.")

    lines.append(f"\nError: {error}")
    return "\n".join(lines)


async def _stream_with_fallback(
    *,
    prompt: str,
    fast: str,
    chosen: str,
    thinking: int,
    max_tokens: int,
) -> str:
    try:
        return await gemini_client.stream(
            user=prompt,
            model=chosen,
            system=LEMO_SYSTEM_PROMPT,
            temperature=0.5,
            max_output_tokens=max_tokens,
            thinking_budget=thinking,
        )
    except LLMServiceUnavailableError as exc:
        if chosen == fast:
            raise
        logger.warning("[agent=lemo] %s unavailable (%s). Retrying on %s.", chosen, exc, fast)
        return await gemini_client.stream(
            user=prompt,
            model=fast,
            system=LEMO_SYSTEM_PROMPT,
            temperature=0.4,
            max_output_tokens=1024,
            thinking_budget=0,
        )


async def lemo_agent_node(state: LemoState) -> dict:
    user_query = state.get("user_query", "")
    next_action = state.get("next_action", "direct_answer")
    current_product = state.get("current_product")
    scraped = state.get("scraped_data") or []

    prompt = _build_user_message(state)

    pro = gemini_client.pro_model()
    fast = gemini_client.fast_model()
    use_pro = next_action == "discover_and_compare" and len(scraped) > 1
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
            fast=fast,
            chosen=chosen,
            thinking=thinking,
            max_tokens=max_tokens,
        )
        if not answer_text or not answer_text.strip():
            answer_text = "### Update\nI could not generate a response. Please try again."
        logger.info(
            "<<< [3/3] LEMO done in %.0fms -> answer_chars=%d",
            (time.perf_counter() - t0) * 1000,
            len(answer_text),
        )
        errors = state.get("errors") or []
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

    if _is_generic_recommendation_query(user_query) and comparison:
      product_payload = None

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
        "errors": errors,
    }
