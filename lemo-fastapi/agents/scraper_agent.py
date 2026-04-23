"""Scraper agent — second node in the LangGraph pipeline.

Dispatches to one of two strategies based on `next_action`:

    scrape_current_page  -> scrape the active tab and extract structured fields
    discover_and_compare -> ScrapingBee Google SERP (Amazon + Flipkart) + rapidfuzz
                            title filter against the reference product

Emits:
    state["current_product"]        -> structured data for the active page
    state["current_page_context"]   -> raw chunks for Lemo grounding
    state["scraped_data"]           -> ranked list of cross-platform matches
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
from typing import Optional
from urllib.parse import urlparse

from agents.state import LemoState, ScrapedProduct
from helpers.get_product_urls import google_serp_search
from helpers.web_scrapper import web_scrapper

logger = logging.getLogger(__name__)

try:
    from rapidfuzz import fuzz  # type: ignore
except ImportError:  # pragma: no cover
    fuzz = None  # type: ignore


# Any candidate scoring below this vs the reference title is dropped.
# URL-slug fallback uses a lower floor because slugs are noisier than titles.
MATCH_THRESHOLD = 65
URL_SLUG_THRESHOLD = 55

# Stop scraping candidates for a platform once we find one >= this score.
EARLY_EXIT_SCORE = 90

# Number of top SERP results to scrape per platform (higher = better recall,
# slower response). Empirically 3 hits the sweet spot on Amazon/Flipkart.
TOP_N_PER_PLATFORM = 3

# Redis TTL for scraped product pages — comparison results are reusable for
# ~12h before prices typically move on Amazon/Flipkart.
SCRAPE_CACHE_TTL_SECONDS = 12 * 60 * 60

# Shorter TTL for the active tab. Multi-turn chat on one page should reuse the
# scrape, but we don't want to pin stale prices for too long.
CURRENT_PAGE_CACHE_TTL_SECONDS = 15 * 60

_PLATFORM_CATALOG = [
    {"name": "Amazon", "hosts": ["amazon.in", "amazon.com"], "aliases": ["amazon"]},
    {"name": "Flipkart", "hosts": ["flipkart.com"], "aliases": ["flipkart"]},
    {"name": "Myntra", "hosts": ["myntra.com"], "aliases": ["myntra"]},
    {"name": "Ajio", "hosts": ["ajio.com", "allensolly.abfrl.in"], "aliases": ["ajio", "allen solly", "allensolly"]},
    {"name": "Nykaa", "hosts": ["nykaa.com", "nykaafashion.com"], "aliases": ["nykaa", "nykaa fashion"]},
    {"name": "Meesho", "hosts": ["meesho.com"], "aliases": ["meesho"]},
    {"name": "Walmart", "hosts": ["walmart.com"], "aliases": ["walmart"]},
    {"name": "eBay", "hosts": ["ebay.com"], "aliases": ["ebay", "e bay"]},
    {"name": "Etsy", "hosts": ["etsy.com"], "aliases": ["etsy"]},
]


def _platform_for_host(host: str) -> dict | None:
    lowered = (host or "").lower()
    for platform in _PLATFORM_CATALOG:
        if any(candidate in lowered for candidate in platform["hosts"]):
            return platform
    return None


def _platform_name_for_url(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return "Unknown"
    platform = _platform_for_host(host)
    return platform["name"] if platform else "Unknown"


def _default_platforms_for_url(url: str) -> list[dict]:
    host = urlparse(url).netloc.lower() if url else ""
    current_platform = _platform_for_host(host)
    india = host.endswith(".in") or any(token in host for token in ("flipkart", "myntra", "ajio", "nykaa", "meesho"))
    names = (
        ["Amazon", "Flipkart", "Myntra", "Ajio", "Nykaa", "Meesho"]
        if india else
        ["Amazon", "Walmart", "eBay", "Etsy"]
    )
    selected: list[dict] = []
    seen: set[str] = set()
    if current_platform:
        selected.append(current_platform)
        seen.add(current_platform["name"])
    for platform in _PLATFORM_CATALOG:
        if platform["name"] in names and platform["name"] not in seen:
            selected.append(platform)
            seen.add(platform["name"])
    return selected


def _platforms_for_query(user_query: str, current_url: str) -> list[dict]:
    lowered = (user_query or "").lower()
    selected: list[dict] = []
    seen: set[str] = set()
    explicit_match = False

    current_platform = _platform_for_host(urlparse(current_url).netloc.lower() if current_url else "")
    if current_platform:
        selected.append(current_platform)
        seen.add(current_platform["name"])

    for platform in _PLATFORM_CATALOG:
        if platform["name"] in seen:
            continue
        aliases = [platform["name"].lower(), *platform["aliases"]]
        if any(alias in lowered for alias in aliases):
            selected.append(platform)
            seen.add(platform["name"])
            explicit_match = True

    if explicit_match:
        return selected
    return _default_platforms_for_url(current_url)


# ---------------------------------------------------------------------------
# Helpers — shared with cases/asking.py (kept independent to avoid coupling)
# ---------------------------------------------------------------------------


def _extract_field(label: str, context_text: str) -> Optional[str]:
    match = re.search(
        rf"{label}:\s*(.+?)(?:\s+\|\s+|$)",
        context_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return None
    value = " ".join(match.group(1).split())
    return value[:300] if value else None


def _extract_numeric_rating(raw_rating: Optional[str]) -> str:
    if not raw_rating:
        return ""
    match = re.search(r"(\d+(?:\.\d+)?)", raw_rating)
    return match.group(1) if match else raw_rating


def _normalize_price(raw_price: Optional[str]) -> str:
    if not raw_price:
        return ""
    cleaned = " ".join(raw_price.split())
    if cleaned.startswith(("₹", "$")):
        return cleaned
    if re.search(r"\d", cleaned):
        return f"₹{cleaned}"
    return cleaned


def _extract_model_hint(text: str) -> str:
    if not text:
        return ""
    candidates = re.findall(r"\b[A-Z0-9]{6,}\b", text.upper())
    return candidates[0] if candidates else ""


def _payload_from_chunks(url: str, chunks: list[str]) -> ScrapedProduct:
    context_text = "\n".join(chunks[:3]) if chunks else ""
    title = _extract_field("PRODUCT TITLE", context_text) or ""
    price_raw = _extract_field("PRICE", context_text)
    rating_raw = _extract_field("RATING", context_text)
    reviews = _extract_field("REVIEWS", context_text) or ""
    features = _extract_field("FEATURES", context_text) or ""
    description = _extract_field("DESCRIPTION", context_text) or ""

    return {
        "platform": _platform_name_for_url(url),
        "title": title,
        "price": _normalize_price(price_raw),
        "rating": _extract_numeric_rating(rating_raw),
        "rating_text": rating_raw or "",
        "reviewCount": reviews,
        "description": (description or features)[:500],
        "features": features[:800],
        "image": "",
        "url": url,
        "match_score": 100.0,  # overridden for cross-platform matches
    }


# ---------------------------------------------------------------------------
# Strategy 1 — scrape the active tab
# ---------------------------------------------------------------------------


_NON_SCRAPABLE = (
    "chrome://",
    "chrome-extension://",
    "about:",
    "file://",
    "data:",
    "javascript:",
    "edge://",
    "brave://",
)


async def _scrape_current_page(state: LemoState) -> dict:
    url = state.get("current_page_url", "") or ""
    if not url or any(url.lower().startswith(s) for s in _NON_SCRAPABLE):
        return {
            "current_product": None,
            "current_page_context": "",
            "scraped_data": [],
            "errors": (state.get("errors") or []) + ["scraper: non-scrapable URL"],
        }

    # Multi-turn chat on the same URL should reuse the scrape rather than
    # spending another 10-12s on ScrapingBee. Cache both the structured product
    # and the raw context so the Lemo agent gets identical grounding on replay.
    cached = await _load_scraped_cache(url, namespace="current_page")
    if cached and cached.get("current_product"):
        logger.info(
            "[agent=scraper] current-page CACHE HIT title=%r price=%s",
            (cached["current_product"].get("title") or "")[:60],
            cached["current_product"].get("price"),
        )
        return {
            "current_product": cached["current_product"],
            "current_page_context": cached.get("current_page_context", ""),
            "scraped_data": cached.get("scraped_data") or [],
        }

    try:
        chunks = await web_scrapper(url, full_page=True)
    except Exception as exc:
        logger.warning("[agent=scraper] current-page scrape failed for %s: %s", url, exc)
        return {
            "current_product": None,
            "current_page_context": "",
            "scraped_data": [],
            "errors": (state.get("errors") or []) + [f"scraper: {exc}"],
        }

    if not chunks:
        return {
            "current_product": None,
            "current_page_context": "",
            "scraped_data": [],
        }

    product = _payload_from_chunks(url, chunks if isinstance(chunks, list) else [chunks])
    context_text = "\n\n".join(chunks[:5]) if isinstance(chunks, list) else str(chunks)

    logger.info(
        "[agent=scraper] current-page ok: title=%r price=%s",
        (product.get("title") or "")[:60],
        product.get("price"),
    )

    result = {
        "current_product": product,
        "current_page_context": context_text,
        "scraped_data": [product] if product.get("title") else [],
    }

    if product.get("title"):
        await _store_scraped_cache(
            url, result, ttl_seconds=CURRENT_PAGE_CACHE_TTL_SECONDS,
            namespace="current_page",
        )

    return result


# ---------------------------------------------------------------------------
# Strategy 2 — cross-platform discover & compare
# ---------------------------------------------------------------------------


def _fuzzy_score(reference: str, candidate: str) -> float:
    if not reference or not candidate:
        return 0.0
    if fuzz is None:
        a = reference.lower()
        b = candidate.lower()
        return 100.0 if a in b or b in a else 40.0
    return float(fuzz.token_set_ratio(reference, candidate))


def _url_slug_tokens(url: str) -> str:
    """Extract a human-readable slug from a product URL for fuzzy fallback.

    Flipkart URLs look like /apple-iphone-17e-white-512-gb/p/itm... ; Amazon
    ones like /Apple-iPhone-17e-512-GB/dp/... . The slug is the last
    informative segment before `/p/` or `/dp/`.
    """
    try:
        path = urlparse(url).path
    except Exception:
        return ""
    parts = [seg for seg in path.split("/") if seg]
    if not parts:
        return ""
    slug = ""
    for i, seg in enumerate(parts):
        if seg.lower() in {"p", "dp"} and i > 0:
            slug = parts[i - 1]
            break
    if not slug:
        slug = max(parts, key=len)
    slug = re.sub(r"[-_]+", " ", slug)
    slug = re.sub(r"\s+", " ", slug).strip()
    return slug


# ---------------------------------------------------------------------------
# Redis-backed scraped-page cache (12h TTL)
# ---------------------------------------------------------------------------


def _scrape_cache_key(url: str, namespace: str = "product") -> str:
    return f"scrape:{namespace}:{hashlib.md5(url.encode('utf-8')).hexdigest()}"


async def _load_scraped_cache(url: str, namespace: str = "product") -> Optional[dict]:
    try:
        from helpers.redis_functions import get_redis_connection

        r = await get_redis_connection()
        try:
            raw = await r.get(_scrape_cache_key(url, namespace))
        finally:
            await r.close()
        if not raw:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return json.loads(raw)
    except Exception as exc:
        logger.debug("[agent=scraper] scrape cache read skipped: %s", exc)
        return None


async def _store_scraped_cache(
    url: str,
    payload: dict,
    ttl_seconds: int = SCRAPE_CACHE_TTL_SECONDS,
    namespace: str = "product",
) -> None:
    try:
        from helpers.redis_functions import get_redis_connection

        r = await get_redis_connection()
        try:
            await r.setex(
                _scrape_cache_key(url, namespace), ttl_seconds, json.dumps(payload)
            )
        finally:
            await r.close()
    except Exception as exc:
        logger.debug("[agent=scraper] scrape cache write skipped: %s", exc)


async def _scrape_and_score(url: str, reference_title: str) -> Optional[ScrapedProduct]:
    """Scrape one candidate URL and score it against the reference title.

    Uses a 12h Redis cache keyed by URL. When the extractor can't find a
    title (common for JS-heavy sites on the first hit), we fall back to
    scoring the URL slug so genuinely-relevant candidates aren't dropped
    to score=0.
    """
    cached = await _load_scraped_cache(url)
    if cached:
        cached = dict(cached)  # type: ignore[arg-type]
        score = _fuzzy_score(reference_title, cached.get("title") or "")
        if not cached.get("title"):
            slug = _url_slug_tokens(url)
            slug_score = _fuzzy_score(reference_title, slug)
            if slug_score > score:
                score = slug_score * 0.85  # discount slug-only matches
        cached["match_score"] = round(score, 2)
        logger.info("[agent=scraper] cache hit %s score=%.1f", url[:90], score)
        return cached  # type: ignore[return-value]

    try:
        chunks = await web_scrapper(url, full_page=True)
    except Exception as exc:
        logger.warning("[agent=scraper] scrape failed for %s: %s", url[:90], exc)
        return None
    if not chunks:
        return None

    payload = _payload_from_chunks(url, chunks if isinstance(chunks, list) else [chunks])
    title_score = _fuzzy_score(reference_title, payload.get("title") or "")
    final_score = title_score

    # URL-slug fallback: many SPAs (Flipkart first paint, Myntra, etc.) hand
    # us an empty title on one pass. Rather than drop a legitimate candidate,
    # score its slug against the reference and apply a 0.85x discount so
    # title-hit pages still win ties.
    if not payload.get("title") or title_score < URL_SLUG_THRESHOLD:
        slug = _url_slug_tokens(url)
        slug_score = _fuzzy_score(reference_title, slug) * 0.85
        if slug_score > final_score:
            final_score = slug_score
            if not payload.get("title"):
                payload["title"] = slug.title()

    payload["match_score"] = round(final_score, 2)
    await _store_scraped_cache(url, payload)
    return payload


async def _discover_and_compare(state: LemoState) -> dict:
    # 1) Ensure we know the reference product — scrape current page if we haven't already.
    current_product = state.get("current_product")
    current_context = state.get("current_page_context", "")
    if current_product is None:
        sub = await _scrape_current_page(state)
        current_product = sub.get("current_product")
        current_context = sub.get("current_page_context", "")

    reference_title = (current_product or {}).get("title") or ""
    query_for_scraper = state.get("query_for_scraper") or ""
    user_query = state.get("user_query", "") or ""

    # 2) Build a CLEAN query — prefer the title from scraped data, not raw user text.
    search_query = query_for_scraper.strip() or reference_title.strip()
    if not search_query:
        # Fall back to user's words only as a last resort.
        search_query = user_query.strip()
    model_hint = _extract_model_hint(reference_title) or _extract_model_hint(current_context)
    if model_hint and model_hint.lower() not in search_query.lower():
        search_query = f"{search_query} {model_hint}".strip()

    if not search_query:
        return {
            "current_product": current_product,
            "current_page_context": current_context,
            "scraped_data": [],
            "errors": (state.get("errors") or []) + ["scraper: no search query"],
        }

    # 3) Decide which platforms to query — if the user named one explicitly, respect it.
    platforms = _platforms_for_query(user_query, state.get("current_page_url", "") or "")

    logger.info(
        "[agent=scraper] discover_and_compare query=%r platforms=%s",
        search_query[:80],
        [p["name"] for p in platforms],
    )

    # 4) Run SERP per platform in parallel, collect a global candidate list,
    #    dedup, then scrape every candidate concurrently. That's materially
    #    faster than the old sequential-per-platform loop and lets us early-
    #    exit as soon as a strong match lands.
    current_url = state.get("current_page_url", "") or ""
    current_platform_name = _platform_name_for_url(current_url)

    async def _candidates_for(platform: dict) -> list[tuple[str, str]]:
        platform_name = platform["name"]
        urls: list[str] = []
        if platform_name == current_platform_name and current_url:
            urls.append(current_url)
        for host in platform["hosts"]:
            serp = await google_serp_search(search_query, site=host, limit=TOP_N_PER_PLATFORM)
            urls.extend(serp.get("urls", [])[:TOP_N_PER_PLATFORM])

        deduped: list[str] = []
        seen: set[str] = set()
        for candidate_url in urls:
            if candidate_url in seen:
                continue
            seen.add(candidate_url)
            deduped.append(candidate_url)
        return [(platform_name, u) for u in deduped[:TOP_N_PER_PLATFORM]]

    candidate_groups = await asyncio.gather(
        *[_candidates_for(platform) for platform in platforms],
        return_exceptions=False,
    )
    # Flatten + dedup URLs while preserving first-platform-seen ordering.
    seen_urls: set[str] = set()
    candidates: list[tuple[str, str]] = []
    for group in candidate_groups:
        for platform_name, url in group:
            if url in seen_urls:
                continue
            seen_urls.add(url)
            candidates.append((platform_name, url))

    if not candidates:
        logger.info("[agent=scraper] no SERP candidates for %r", search_query[:80])
        return {
            "current_product": current_product,
            "current_page_context": current_context,
            "scraped_data": [],
        }

    logger.info(
        "[agent=scraper] scraping %d candidates in parallel (platforms=%s)",
        len(candidates), [p["name"] for p in platforms],
    )

    async def _score_one(platform_name: str, url: str) -> Optional[ScrapedProduct]:
        payload = await _scrape_and_score(url, reference_title or search_query)
        if not payload:
            return None
        payload["platform"] = platform_name
        return payload

    scrape_tasks = [_score_one(name, url) for name, url in candidates]
    raw_results: list[Optional[ScrapedProduct]] = await asyncio.gather(
        *scrape_tasks, return_exceptions=False
    )

    # Group by platform, keep best-scoring candidate per platform.
    best_by_platform: dict[str, ScrapedProduct] = {}
    if current_product and current_product.get("title"):
        seeded = dict(current_product)
        seeded["platform"] = current_product.get("platform") or current_platform_name or "Current Site"
        seeded["match_score"] = 100.0
        best_by_platform[seeded["platform"]] = seeded  # type: ignore[assignment]
    for payload in raw_results:
        if not payload:
            continue
        platform = payload.get("platform") or "Unknown"
        if payload["match_score"] < MATCH_THRESHOLD and reference_title:
            logger.info(
                "[agent=scraper] drop %-8s score=%.1f < %d title=%r",
                platform,
                payload["match_score"],
                MATCH_THRESHOLD,
                (payload.get("title") or "")[:60],
            )
            continue
        current = best_by_platform.get(platform)
        if current is None or payload["match_score"] > current.get("match_score", 0):
            best_by_platform[platform] = payload
            logger.info(
                "[agent=scraper] keep %-8s score=%.1f price=%s title=%r",
                platform,
                payload["match_score"],
                payload.get("price") or "-",
                (payload.get("title") or "")[:60],
            )

    # Preserve the order in which platforms were requested so UI stays stable.
    scraped_data: list[ScrapedProduct] = [
        best_by_platform[platform["name"]] for platform in platforms if platform["name"] in best_by_platform
    ]

    logger.info(
        "[agent=scraper] discover_and_compare finished: %d matches across %d platforms",
        len(scraped_data), len(platforms),
    )

    return {
        "current_product": current_product,
        "current_page_context": current_context,
        "scraped_data": scraped_data,
    }


# ---------------------------------------------------------------------------
# LangGraph node entry point
# ---------------------------------------------------------------------------


async def scraper_agent_node(state: LemoState) -> dict:
    next_action = state.get("next_action", "direct_answer")

    logger.info(">>> [2/3] SCRAPER (next_action=%s)", next_action)
    t0 = time.perf_counter()

    if next_action == "scrape_current_page":
        out = await _scrape_current_page(state)
    elif next_action == "discover_and_compare":
        out = await _discover_and_compare(state)
    else:
        logger.debug("[agent=scraper] noop for next_action=%s", next_action)
        return {}

    cp = out.get("current_product") or {}
    sd = out.get("scraped_data") or []
    logger.info(
        "<<< [2/3] SCRAPER done in %.0fms -> current=%r price=%s scraped=%d",
        (time.perf_counter() - t0) * 1000,
        (cp.get("title") or "")[:60],
        cp.get("price"),
        len(sd),
    )
    for i, p in enumerate(sd[:5], 1):
        logger.info(
            "    [%d] %-10s %s | %s | score=%s",
            i,
            p.get("platform") or "?",
            (p.get("title") or "")[:60],
            p.get("price") or "-",
            p.get("match_score"),
        )
    return out
