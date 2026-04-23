"""Legacy product_recommendation retained for backward compatibility.

The new multi-agent pipeline handles product discovery inside
`agents/scraper_agent.py`, which uses the ScrapingBee Google SERP + rapidfuzz
title matching. Embeddings are no longer used for product matching (they are
unreliable for this task, as documented in the debug guide).

This module is kept so `cases/asking.py` — the legacy fallback — keeps
working for direct callers. It now returns a ranked list of scraped product
dicts ordered by fuzzy title match.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from helpers.get_product_urls import google_serp_search  # noqa: E402
from helpers.web_scrapper import web_scrapper  # noqa: E402

logger = logging.getLogger(__name__)

try:
    from rapidfuzz import fuzz  # type: ignore
except ImportError:  # pragma: no cover
    fuzz = None  # type: ignore


MATCH_THRESHOLD = 60  # a bit looser than the scraper agent since there's no reference title


def _title_from_chunks(chunks) -> str:
    if not chunks:
        return ""
    text = chunks[0] if isinstance(chunks, list) else str(chunks)
    match = re.search(r"PRODUCT TITLE:\s*(.+?)(?:\s+\|\s+|$)", text, flags=re.IGNORECASE)
    if match:
        return " ".join(match.group(1).split())[:200]
    return ""


async def product_recommendation(domain: str, user_query: str):
    """Return a list of candidate product URLs ranked by fuzzy title match.

    Returns a list[str] of URLs (ordered, best first) to stay compatible with
    the legacy `product_recommendation_prompt` which iterates URL strings.
    """
    logger.info(
        "[product_recommendation] domain=%s query=%r (rule-based, no embeddings)",
        domain,
        user_query[:80],
    )

    try:
        serp = await google_serp_search(user_query, site=domain or None, limit=10)
    except Exception as exc:
        logger.warning("[product_recommendation] SERP failed: %s", exc)
        return []

    urls = serp.get("urls") or []
    if not urls:
        logger.warning("[product_recommendation] No product URLs returned")
        return []

    async def _scrape_one(url: str) -> dict | None:
        try:
            chunks = await web_scrapper(url)
        except Exception as exc:
            logger.debug("[product_recommendation] scrape failed for %s: %s", url, exc)
            return None
        if not chunks:
            return None
        title = _title_from_chunks(chunks if isinstance(chunks, list) else [chunks])
        return {"url": url, "title": title, "chunk": chunks}

    scraped = await asyncio.gather(*[_scrape_one(u) for u in urls], return_exceptions=False)

    ranked: list[dict] = []
    for entry in scraped:
        if not entry:
            continue
        title = entry.get("title") or ""
        # Use fuzzy match vs the user's query as a weak relevance signal.
        if fuzz is not None:
            score = float(fuzz.token_set_ratio(user_query, title)) if title else 0.0
        else:
            score = 100.0 if user_query.lower() in (title or "").lower() else 40.0
        if score < MATCH_THRESHOLD and title:
            continue
        ranked.append({"url": entry["url"], "title": title, "score": round(score, 2)})

    ranked.sort(key=lambda r: r["score"], reverse=True)
    logger.info("[product_recommendation] returning %d ranked candidates", len(ranked))
    return [r["url"] for r in ranked[:10]]
