"""Scraper agent — second node in the LangGraph pipeline."""

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


MATCH_THRESHOLD = 65
URL_SLUG_THRESHOLD = 55
TOP_N_PER_PLATFORM = 3
SCRAPE_CACHE_TTL_SECONDS = 12 * 60 * 60
CURRENT_PAGE_CACHE_TTL_SECONDS = 15 * 60
SCRAPE_CONCURRENCY = 4

APPLIANCE_KEYWORDS = {
    "refrigerator", "fridge", "double door", "single door", "frost free", "washing machine",
    "air conditioner", "ac", "cooler", "television", "tv", "microwave", "oven",
}
FASHION_KEYWORDS = {
    "shirt", "t-shirt", "dress", "jeans", "sneakers", "shoes", "watch", "kurta", "jacket",
}
BEAUTY_KEYWORDS = {
    "lipstick", "serum", "cream", "makeup", "skincare", "perfume", "moisturizer",
}

_PLATFORM_CATALOG = [
    {"name": "Amazon", "hosts": ["amazon.in", "amazon.com"], "aliases": ["amazon"], "verticals": {"general", "appliances", "fashion", "beauty"}},
    {"name": "Flipkart", "hosts": ["flipkart.com"], "aliases": ["flipkart"], "verticals": {"general", "appliances", "fashion", "electronics"}},
    {"name": "Meesho", "hosts": ["meesho.com"], "aliases": ["meesho"], "verticals": {"general", "appliances", "fashion", "beauty"}},
    {"name": "Myntra", "hosts": ["myntra.com"], "aliases": ["myntra"], "verticals": {"fashion"}},
    {"name": "Ajio", "hosts": ["ajio.com", "allensolly.abfrl.in"], "aliases": ["ajio", "allen solly", "allensolly"], "verticals": {"fashion"}},
    {"name": "Nykaa", "hosts": ["nykaa.com", "nykaafashion.com"], "aliases": ["nykaa", "nykaa fashion"], "verticals": {"beauty", "fashion"}},
    {"name": "Walmart", "hosts": ["walmart.com"], "aliases": ["walmart"], "verticals": {"general", "appliances"}},
    {"name": "eBay", "hosts": ["ebay.com"], "aliases": ["ebay", "e bay"], "verticals": {"general", "appliances", "fashion"}},
    {"name": "Etsy", "hosts": ["etsy.com"], "aliases": ["etsy"], "verticals": {"general", "fashion"}},
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


def _token_set(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(token) > 1}


def _infer_vertical(*texts: str) -> str:
    tokens = set()
    for text in texts:
        tokens |= _token_set(text)
    joined = " ".join(sorted(tokens))
    if any(keyword in joined for keyword in APPLIANCE_KEYWORDS):
        return "appliances"
    if any(keyword in joined for keyword in BEAUTY_KEYWORDS):
        return "beauty"
    if any(keyword in joined for keyword in FASHION_KEYWORDS):
        return "fashion"
    return "general"


def _default_platform_names(vertical: str, current_url: str) -> list[str]:
    host = urlparse(current_url).netloc.lower() if current_url else ""
    india = host.endswith(".in") or any(token in host for token in ("flipkart", "myntra", "ajio", "nykaa", "meesho"))
    if vertical == "appliances":
        return ["Amazon", "Flipkart", "Meesho"] if india else ["Amazon", "Walmart", "eBay"]
    if vertical == "fashion":
        return ["Myntra", "Ajio", "Amazon", "Meesho"] if india else ["Amazon", "eBay", "Etsy"]
    if vertical == "beauty":
        return ["Nykaa", "Amazon", "Meesho"] if india else ["Amazon", "eBay"]
    return ["Amazon", "Flipkart", "Meesho"] if india else ["Amazon", "Walmart", "eBay"]


def _platforms_for_query(user_query: str, current_url: str, current_product: dict | None) -> list[dict]:
    lowered = (user_query or "").lower()
    current_platform = _platform_for_host(urlparse(current_url).netloc.lower() if current_url else "")
    vertical = _infer_vertical(user_query, (current_product or {}).get("title", ""), current_url)

    mentioned: list[dict] = []
    for platform in _PLATFORM_CATALOG:
        aliases = [platform["name"].lower(), *platform["aliases"]]
        if any(alias in lowered for alias in aliases):
            if vertical in platform["verticals"] or "general" in platform["verticals"]:
                mentioned.append(platform)

    only_markers = (" only", " only.", " only ", " just ", " specifically ")
    if mentioned and any(marker in lowered for marker in only_markers):
        return mentioned

    if mentioned:
        names = {platform["name"] for platform in mentioned}
        if current_platform and current_platform["name"] not in names and (vertical in current_platform["verticals"] or "general" in current_platform["verticals"]):
            mentioned.insert(0, current_platform)
        return mentioned

    defaults = []
    wanted_names = set(_default_platform_names(vertical, current_url))
    if current_platform and current_platform["name"] in wanted_names:
        defaults.append(current_platform)
    seen = {p["name"] for p in defaults}
    for platform in _PLATFORM_CATALOG:
        if platform["name"] in seen:
            continue
        if platform["name"] in wanted_names and (vertical in platform["verticals"] or "general" in platform["verticals"]):
            defaults.append(platform)
            seen.add(platform["name"])
    return defaults


def _query_refers_to_current_product(user_query: str, current_product: dict | None) -> bool:
    lowered = (user_query or "").lower()
    if any(token in lowered for token in (
        "this product", "this item", "current product", "same product", "similar product",
        "same features", "with respect to", "difference", "compare", "alternative", "cheaper",
    )):
        return True
    title = (current_product or {}).get("title") or ""
    model_hint = _extract_model_hint(title)
    return bool(model_hint and model_hint.lower() in lowered)


def _budget_cap_from_query(user_query: str, current_product: dict | None) -> float | None:
    lowered = (user_query or "").lower()

    if "price cap as this current product" in lowered or "price cap as this product" in lowered:
        return _price_value((current_product or {}).get("price"))

    between = re.search(r"between\s*(?:rs\.?|₹)?\s*([\d,]+)\s*(?:to|-)\s*(?:rs\.?|₹)?\s*([\d,]+)", lowered)
    if between:
        try:
            return float(between.group(2).replace(",", ""))
        except ValueError:
            return None

    under = re.search(r"(?:under|below|less than|max(?:imum)?(?: budget)?|upto|up to)\s*(?:rs\.?|₹)?\s*([\d,]+)", lowered)
    if under:
        try:
            return float(under.group(1).replace(",", ""))
        except ValueError:
            return None

    return None


def _price_value(raw_price: Optional[str]) -> float | None:
    if raw_price is None:
        return None
    if isinstance(raw_price, (int, float)):
        return float(raw_price)
    text = str(raw_price).replace(",", "")
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _is_recommendation_query(user_query: str) -> bool:
    lowered = (user_query or "").lower()
    return any(token in lowered for token in ("suggest", "recommend", "best ", "budget", "buy a ", "i want to buy", "looking for"))


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
        "match_score": 100.0,
    }


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
        return {"current_product": None, "current_page_context": "", "scraped_data": []}

    product = _payload_from_chunks(url, chunks if isinstance(chunks, list) else [chunks])
    context_text = "\n\n".join(chunks[:5]) if isinstance(chunks, list) else str(chunks)

    result = {
        "current_product": product,
        "current_page_context": context_text,
        "scraped_data": [product] if product.get("title") else [],
    }

    if product.get("title"):
        await _store_scraped_cache(url, result, ttl_seconds=CURRENT_PAGE_CACHE_TTL_SECONDS, namespace="current_page")
    return result


def _fuzzy_score(reference: str, candidate: str) -> float:
    if not reference or not candidate:
        return 0.0
    if fuzz is None:
        a = reference.lower()
        b = candidate.lower()
        return 100.0 if a in b or b in a else 40.0
    return float(fuzz.token_set_ratio(reference, candidate))


def _url_slug_tokens(url: str) -> str:
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


def _scrape_cache_key(url: str, namespace: str = "product") -> str:
    return f"scrape:{namespace}:{hashlib.md5(url.encode('utf-8')).hexdigest()}"


async def _load_scraped_cache(url: str, namespace: str = "product") -> Optional[dict]:
    try:
        from helpers import runtime_cache

        return await runtime_cache.get_json(_scrape_cache_key(url, namespace))
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
        from helpers import runtime_cache

        await runtime_cache.set_json(_scrape_cache_key(url, namespace), payload, ttl_seconds)
    except Exception as exc:
        logger.debug("[agent=scraper] scrape cache write skipped: %s", exc)


async def _scrape_and_score(url: str, reference_title: str) -> Optional[ScrapedProduct]:
    cached = await _load_scraped_cache(url)
    if cached:
        cached = dict(cached)  # type: ignore[arg-type]
        score = _fuzzy_score(reference_title, cached.get("title") or "")
        if not cached.get("title"):
            slug = _url_slug_tokens(url)
            slug_score = _fuzzy_score(reference_title, slug)
            if slug_score > score:
                score = slug_score * 0.85
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


def _payload_within_budget(payload: ScrapedProduct, budget_cap: float | None) -> bool:
    if budget_cap is None:
        return True
    value = _price_value(payload.get("price"))
    return value is not None and value <= budget_cap


def _payload_matches_vertical(payload: ScrapedProduct, vertical: str) -> bool:
    if vertical == "general":
        return True
    title = (payload.get("title") or "").lower()
    description = (payload.get("description") or "").lower()
    haystack = f"{title} {description}"
    if vertical == "appliances":
        return any(keyword in haystack for keyword in APPLIANCE_KEYWORDS)
    if vertical == "fashion":
        return any(keyword in haystack for keyword in FASHION_KEYWORDS)
    if vertical == "beauty":
        return any(keyword in haystack for keyword in BEAUTY_KEYWORDS)
    return True


async def _discover_and_compare(state: LemoState) -> dict:
    current_product = state.get("current_product")
    current_context = state.get("current_page_context", "")
    if current_product is None:
        sub = await _scrape_current_page(state)
        current_product = sub.get("current_product")
        current_context = sub.get("current_page_context", "")

    user_query = state.get("user_query", "") or ""
    anchored_to_current = _query_refers_to_current_product(user_query, current_product)
    budget_cap = _budget_cap_from_query(user_query, current_product)
    vertical = _infer_vertical(user_query, (current_product or {}).get("title", ""), current_context)

    reference_title = (current_product or {}).get("title") or ""
    query_for_scraper = state.get("query_for_scraper") or ""
    search_query = (query_for_scraper if query_for_scraper.strip() else (reference_title if anchored_to_current else user_query)).strip()
    if anchored_to_current:
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

    platforms = _platforms_for_query(user_query, state.get("current_page_url", "") or "", current_product)
    logger.info(
        "[agent=scraper] discover_and_compare query=%r platforms=%s anchored=%s budget_cap=%s vertical=%s",
        search_query[:100],
        [p["name"] for p in platforms],
        anchored_to_current,
        budget_cap,
        vertical,
    )

    current_url = state.get("current_page_url", "") or ""
    current_platform_name = _platform_name_for_url(current_url)

    async def _candidates_for(platform: dict) -> list[tuple[str, str]]:
        platform_name = platform["name"]
        urls: list[str] = []
        if anchored_to_current and platform_name == current_platform_name and current_url:
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

    candidate_groups = await asyncio.gather(*[_candidates_for(platform) for platform in platforms], return_exceptions=False)
    seen_urls: set[str] = set()
    candidates: list[tuple[str, str]] = []
    for group in candidate_groups:
        for platform_name, url in group:
            if url in seen_urls:
                continue
            seen_urls.add(url)
            candidates.append((platform_name, url))

    if not candidates:
        return {"current_product": current_product, "current_page_context": current_context, "scraped_data": []}

    logger.info("[agent=scraper] scraping %d candidates in parallel (platforms=%s)", len(candidates), [p["name"] for p in platforms])

    semaphore = asyncio.Semaphore(SCRAPE_CONCURRENCY)
    reference = reference_title or search_query

    async def _score_one(platform_name: str, url: str) -> Optional[ScrapedProduct]:
        async with semaphore:
            payload = await _scrape_and_score(url, reference)
        if not payload:
            return None
        payload["platform"] = platform_name
        return payload

    raw_results: list[Optional[ScrapedProduct]] = await asyncio.gather(*[_score_one(name, url) for name, url in candidates], return_exceptions=False)

    best_by_platform: dict[str, ScrapedProduct] = {}
    if anchored_to_current and current_product and current_product.get("title") and _payload_within_budget(current_product, budget_cap):
        seeded = dict(current_product)
        seeded["platform"] = current_product.get("platform") or current_platform_name or "Current Site"
        seeded["match_score"] = 100.0
        best_by_platform[seeded["platform"]] = seeded  # type: ignore[assignment]

    for payload in raw_results:
        if not payload:
            continue
        platform = payload.get("platform") or "Unknown"
        if reference and payload["match_score"] < MATCH_THRESHOLD:
            logger.info("[agent=scraper] drop %-8s score=%.1f < %d title=%r", platform, payload["match_score"], MATCH_THRESHOLD, (payload.get("title") or "")[:60])
            continue
        if not _payload_matches_vertical(payload, vertical):
            logger.info("[agent=scraper] drop %-8s wrong vertical title=%r", platform, (payload.get("title") or "")[:70])
            continue
        if not _payload_within_budget(payload, budget_cap):
            logger.info("[agent=scraper] drop %-8s over budget price=%s cap=%s", platform, payload.get("price"), budget_cap)
            continue
        current = best_by_platform.get(platform)
        if current is None or payload["match_score"] > current.get("match_score", 0):
            best_by_platform[platform] = payload
            logger.info("[agent=scraper] keep %-8s score=%.1f price=%s title=%r", platform, payload["match_score"], payload.get("price") or "-", (payload.get("title") or "")[:60])

    scraped_data: list[ScrapedProduct] = [best_by_platform[p["name"]] for p in platforms if p["name"] in best_by_platform]

    return {
        "current_product": current_product,
        "current_page_context": current_context,
        "scraped_data": scraped_data,
    }


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
