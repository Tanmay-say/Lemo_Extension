"""Product URL discovery."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
from typing import Optional
from urllib.parse import quote, quote_plus, unquote, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from ddgs import DDGS

logger = logging.getLogger(__name__)

SERP_CACHE_TTL_SECONDS = 6 * 60 * 60

SCRAPINGBEE_API_KEY = os.getenv("SCRAPINGBEE_API_KEY", "").strip()
if SCRAPINGBEE_API_KEY.startswith("PLACEHOLDER"):
    SCRAPINGBEE_API_KEY = ""


SITE_PATTERNS = {
    "myntra.com": {"sp_check": lambda url: "/buy" in url},
    "ajio.com": {"sp_check": lambda url: "/p/" in url},
    "nykaafashion.com": {"sp_check": lambda url: "/p/" in url},
    "nykaa.com": {"sp_check": lambda url: "/p/" in url},
    "amazon.in": {"sp_check": lambda url: "/dp/" in url},
    "amazon.com": {"sp_check": lambda url: "/dp/" in url},
    "flipkart.com": {"sp_check": lambda url: "/p/" in url},
    "meesho.com": {"sp_check": lambda url: "/p/" in url},
    "allensolly.abfrl.in": {"sp_check": lambda url: "/p/" in url},
}


def is_product_page(url, site=None):
    lowered = (url or "").lower()
    if not lowered.startswith("http"):
        return False
    if not site:
        for domain, patterns in SITE_PATTERNS.items():
            if domain in lowered:
                return patterns["sp_check"](lowered)
        return True
    for domain, patterns in SITE_PATTERNS.items():
        if domain in (site or "").lower() and domain in lowered:
            return patterns["sp_check"](lowered)
    return site.lower() in lowered


def categorize_urls(urls, site=None):
    product_pages = []
    list_pages = []
    for url in urls:
        if is_product_page(url, site):
            product_pages.append(url)
        else:
            list_pages.append(url)
    return product_pages, list_pages


def scrape_product_links(list_page_url, site=None, max_links=20):
    product_links: set[str] = set()
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = httpx.get(list_page_url, headers=headers, timeout=10.0, follow_redirects=True)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        for link in soup.find_all("a", href=True):
            absolute_url = urljoin(list_page_url, link["href"])
            if not absolute_url.startswith("http"):
                continue
            if is_product_page(absolute_url, site):
                if not site or site.lower() in absolute_url.lower():
                    product_links.add(absolute_url)
            if len(product_links) >= max_links:
                break
    except Exception:
        pass
    return product_links


def _cache_key(query: str, site: Optional[str]) -> str:
    raw = f"{(site or '').lower()}|{query.strip().lower()}"
    return f"serp:{hashlib.md5(raw.encode('utf-8')).hexdigest()}"


async def _load_serp_cache(query: str, site: Optional[str]) -> list[str] | None:
    try:
        from helpers import runtime_cache

        return await runtime_cache.get_json(_cache_key(query, site))
    except Exception as exc:
        logger.debug("[serp] cache read skipped: %s", exc)
        return None


async def _store_serp_cache(query: str, site: Optional[str], urls: list[str]) -> None:
    try:
        from helpers import runtime_cache

        await runtime_cache.set_json(_cache_key(query, site), urls, SERP_CACHE_TTL_SECONDS)
    except Exception as exc:
        logger.debug("[serp] cache write skipped: %s", exc)


def _build_google_search_term(query: str, site: Optional[str]) -> str:
    return f"site:{site} {query}" if site else query


def _build_google_url(query: str, site: Optional[str], limit: int) -> str:
    return (
        "https://www.google.com/search"
        f"?q={quote_plus(_build_google_search_term(query, site))}"
        f"&num={limit * 2}&hl=en"
    )


def _normalize_candidate_url(url: str) -> str:
    candidate = unquote((url or "").strip())
    if candidate.startswith("/url?q="):
        candidate = candidate.split("/url?q=", 1)[1].split("&", 1)[0]
    return candidate


def _looks_like_search_or_nonproduct(url: str) -> bool:
    lowered = url.lower()
    blocked = (
        "/search",
        "/s?",
        "/s/",
        "/help/",
        "/customer/",
        "/gp/help",
        "/brand/",
        "/brands/",
        "/stores/",
        "/collections/",
        "/appliances-ad/",
        "/c/",
    )
    return any(token in lowered for token in blocked)


def _parse_google_results(html: str, site: Optional[str]) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    urls: list[str] = []
    seen: set[str] = set()

    for a in soup.select("a[href]"):
        href = _normalize_candidate_url(a.get("href", ""))
        if not href.startswith("http"):
            continue
        netloc = urlparse(href).netloc.lower()
        if "google." in netloc or "webcache." in netloc or "gstatic." in netloc:
            continue
        if site and site.lower() not in netloc:
            continue
        if _looks_like_search_or_nonproduct(href):
            continue
        if href in seen:
            continue
        seen.add(href)
        urls.append(href)
    return urls


def _build_scrapingbee_request_url(query: str, site: Optional[str], limit: int) -> str:
    google_url = _build_google_url(query, site, limit)
    encoded_target = quote(google_url, safe=":/")
    country_code = "in" if site and site.endswith(".in") else "us"
    return (
        "https://app.scrapingbee.com/api/v1/"
        f"?api_key={quote(SCRAPINGBEE_API_KEY, safe='')}"
        f"&url={encoded_target}"
        "&render_js=false"
        "&premium_proxy=true"
        f"&country_code={country_code}"
    )


async def _scrapingbee_google_serp(query: str, site: Optional[str], limit: int) -> list[str]:
    request_url = _build_scrapingbee_request_url(query, site, limit)
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        response = await client.get(request_url)
        response.raise_for_status()
        return _parse_google_results(response.text, site)


async def google_serp_search(
    query: str,
    site: Optional[str] = None,
    limit: int = 10,
    *,
    use_cache: bool = True,
) -> dict:
    if not query or not query.strip():
        return {"success": False, "message": "Empty search query", "urls": []}

    if use_cache:
        cached = await _load_serp_cache(query, site)
        if cached:
            logger.info("[serp] cache hit for query=%r site=%s (%d urls)", query[:60], site, len(cached))
            return {"success": bool(cached), "message": "cached", "urls": cached[:limit]}

    if not SCRAPINGBEE_API_KEY:
        logger.info("[serp] SCRAPINGBEE_API_KEY missing, falling back to DDGS")
        return await _ddgs_fallback(query, site, limit)

    try:
        urls = await _scrapingbee_google_serp(query, site, limit)
    except Exception as exc:
        logger.warning("[serp] ScrapingBee Google SERP failed: %s - falling back to DDGS", exc)
        return await _ddgs_fallback(query, site, limit)

    product_pages, list_pages = categorize_urls(urls, site)
    if len(product_pages) < limit and list_pages:
        for lp in list_pages:
            if len(product_pages) >= limit:
                break
            for extracted in scrape_product_links(lp, site, max_links=limit - len(product_pages)):
                if extracted not in product_pages:
                    product_pages.append(extracted)

    final = product_pages[:limit]
    if final:
        await _store_serp_cache(query, site, final)

    return {
        "success": bool(final),
        "message": "URLs fetched via ScrapingBee Google SERP" if final else "No product URLs found",
        "urls": final,
    }


async def _ddgs_fallback(query: str, site: Optional[str], limit: int) -> dict:
    def _run() -> list[str]:
        search_query = f"site:{site} {query}" if site else query
        collected: list[str] = []
        seen: set[str] = set()
        try:
            with DDGS() as ddgs:
                for result in ddgs.text(search_query, max_results=limit * 4):
                    url = _normalize_candidate_url(result.get("href") or result.get("link") or "")
                    if not url or not url.startswith("http"):
                        continue
                    if site and site.lower() not in url.lower():
                        continue
                    if _looks_like_search_or_nonproduct(url):
                        continue
                    if url in seen:
                        continue
                    seen.add(url)
                    collected.append(url)
        except Exception as exc:
            logger.warning("[serp] DDGS fallback failed: %s", exc)
        return collected

    try:
        urls = await asyncio.to_thread(_run)
    except Exception as exc:
        logger.warning("[serp] DDGS thread failed: %s", exc)
        urls = []

    product_pages, list_pages = categorize_urls(urls, site)
    if len(product_pages) < limit and list_pages:
        for lp in list_pages:
            if len(product_pages) >= limit:
                break
            for extracted in scrape_product_links(lp, site, max_links=limit - len(product_pages)):
                if extracted not in product_pages:
                    product_pages.append(extracted)

    final = product_pages[:limit]
    if final:
        await _store_serp_cache(query, site, final)
    return {
        "success": bool(final),
        "message": "URLs fetched via DuckDuckGo fallback" if final else "No product URLs found",
        "urls": final,
    }


def browser(query, site=None, limit=10, scrape_lp=True):
    try:
        return asyncio.run(google_serp_search(query, site=site, limit=limit))
    except RuntimeError:
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(
                lambda: asyncio.run(google_serp_search(query, site=site, limit=limit))
            ).result()
