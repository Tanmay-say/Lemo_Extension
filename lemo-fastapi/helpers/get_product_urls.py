"""Product URL discovery.

Primary backend: ScrapingBee's Google SERP (reuses SCRAPINGBEE_API_KEY).
Fallback: DuckDuckGo via the `ddgs` package (rate-limit prone — last resort).

Results are cached in Redis under `serp:<md5(query|site)>` with a 6h TTL so
repeated compare-queries for the same product don't burn ScrapingBee credits.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from typing import Optional
from urllib.parse import quote_plus, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from ddgs import DDGS

logger = logging.getLogger(__name__)

SERP_CACHE_TTL_SECONDS = 6 * 60 * 60  # 6 hours

SCRAPINGBEE_API_KEY = os.getenv("SCRAPINGBEE_API_KEY", "").strip()
if SCRAPINGBEE_API_KEY.startswith("PLACEHOLDER"):
    SCRAPINGBEE_API_KEY = ""


SITE_PATTERNS = {
    'myntra.com': {'sp_check': lambda url: '/buy' in url},
    'ajio.com': {'sp_check': lambda url: '/p/' in url},
    'nykaafashion.com': {'sp_check': lambda url: '/p/' in url},
    'amazon.in': {'sp_check': lambda url: '/dp/' in url},
    'amazon.com': {'sp_check': lambda url: '/dp/' in url},
    'flipkart.com': {'sp_check': lambda url: '/p/' in url},
    'allensolly.abfrl.in': {'sp_check': lambda url: '/p/' in url},
}


# ---------------------------------------------------------------------------
# URL classification
# ---------------------------------------------------------------------------

def is_product_page(url, site=None):
    if not site:
        for domain, patterns in SITE_PATTERNS.items():
            if domain in url.lower():
                return patterns['sp_check'](url)
        return True
    for domain, patterns in SITE_PATTERNS.items():
        if domain in site.lower() and domain in url.lower():
            return patterns['sp_check'](url)
    return True


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
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = httpx.get(list_page_url, headers=headers, timeout=10.0)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        for link in soup.find_all('a', href=True):
            absolute_url = urljoin(list_page_url, link['href'])
            if is_product_page(absolute_url, site):
                if site:
                    if site.lower() in absolute_url.lower():
                        product_links.add(absolute_url)
                else:
                    product_links.add(absolute_url)
            if len(product_links) >= max_links:
                break
    except Exception:
        pass
    return product_links


# ---------------------------------------------------------------------------
# Redis-backed SERP cache
# ---------------------------------------------------------------------------


def _cache_key(query: str, site: Optional[str]) -> str:
    raw = f"{(site or '').lower()}|{query.strip().lower()}"
    return f"serp:{hashlib.md5(raw.encode('utf-8')).hexdigest()}"


async def _load_serp_cache(query: str, site: Optional[str]) -> list[str] | None:
    try:
        from helpers.redis_functions import get_redis_connection

        r = await get_redis_connection()
        try:
            raw = await r.get(_cache_key(query, site))
        finally:
            await r.close()
        if not raw:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return json.loads(raw)
    except Exception as exc:
        logger.debug("[serp] cache read skipped: %s", exc)
        return None


async def _store_serp_cache(query: str, site: Optional[str], urls: list[str]) -> None:
    try:
        from helpers.redis_functions import get_redis_connection

        r = await get_redis_connection()
        try:
            await r.setex(_cache_key(query, site), SERP_CACHE_TTL_SECONDS, json.dumps(urls))
        finally:
            await r.close()
    except Exception as exc:
        logger.debug("[serp] cache write skipped: %s", exc)


# ---------------------------------------------------------------------------
# ScrapingBee Google SERP
# ---------------------------------------------------------------------------


def _build_google_search_term(query: str, site: Optional[str]) -> str:
    """Return the raw (un-encoded) Google `q=` search string."""
    return f"site:{site} {query}" if site else query


def _build_google_url(query: str, site: Optional[str], limit: int) -> str:
    """Return a ready-to-fetch Google SERP URL (used only when we hit Google directly).

    IMPORTANT: do not pass this URL through `httpx`'s `params` dict — that
    would double-encode the query string. Either pass it via `params` using
    the raw search term (see `_build_google_search_term`) or request it directly.
    """
    return (
        f"https://www.google.com/search"
        f"?q={quote_plus(_build_google_search_term(query, site))}"
        f"&num={limit * 2}"
    )


def _parse_google_results(html: str, site: Optional[str]) -> list[str]:
    """Extract organic result URLs from a Google SERP HTML page."""
    soup = BeautifulSoup(html, "html.parser")
    urls: list[str] = []
    seen: set[str] = set()

    for a in soup.select("a[href]"):
        href = a["href"]
        # Google sometimes wraps organic results as /url?q=...
        if href.startswith("/url?q="):
            href = href.split("/url?q=", 1)[1].split("&", 1)[0]
        if not href.startswith("http"):
            continue
        netloc = urlparse(href).netloc.lower()
        # Drop Google's own domains
        if "google." in netloc or "webcache." in netloc or "gstatic." in netloc:
            continue
        if site and site.lower() not in netloc:
            continue
        if href in seen:
            continue
        seen.add(href)
        urls.append(href)
    return urls


async def google_serp_search(
    query: str,
    site: Optional[str] = None,
    limit: int = 10,
    *,
    use_cache: bool = True,
) -> dict:
    """Run a Google SERP lookup via ScrapingBee with a 6h Redis cache.

    Returns `{success, message, urls}` in the same shape as `browser()`.
    """
    if not query or not query.strip():
        return {"success": False, "message": "Empty search query", "urls": []}

    if use_cache:
        cached = await _load_serp_cache(query, site)
        if cached:
            logger.info("[serp] cache hit for query=%r site=%s (%d urls)", query[:60], site, len(cached))
            return {
                "success": bool(cached),
                "message": "cached",
                "urls": cached[:limit],
            }

    if not SCRAPINGBEE_API_KEY:
        logger.info("[serp] SCRAPINGBEE_API_KEY missing, falling back to DDGS")
        return await _ddgs_fallback(query, site, limit)

    # Build the Google URL with exactly one layer of URL encoding; then pass
    # it through ScrapingBee's `url` param as a pre-built (already-encoded)
    # string so httpx doesn't re-encode `%3A`, `%20`, etc. We achieve that by
    # constructing the final request URL ourselves.
    google_url = _build_google_url(query, site, limit)
    scrapingbee_base = "https://app.scrapingbee.com/api/v1/"
    sb_params = {
        "api_key": SCRAPINGBEE_API_KEY,
        "url": google_url,  # httpx will quote this once → safe
        "render_js": "false",
        "premium_proxy": "true",
        "country_code": "in" if site and site.endswith(".in") else "us",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # `params=` on httpx encodes values with `quote_plus`, which turns
            # `%3A` (the already-encoded colon in google_url) into `%253A` —
            # i.e. double encoding. Build the URL with a single `quote` pass
            # by using `httpx.QueryParams` with safe chars, or manually.
            from urllib.parse import urlencode

            request_url = f"{scrapingbee_base}?{urlencode(sb_params, safe=':/?&=%')}"
            response = await client.get(request_url)
            response.raise_for_status()
            html = response.text
    except Exception as exc:
        logger.warning("[serp] ScrapingBee Google SERP failed: %s — falling back to DDGS", exc)
        return await _ddgs_fallback(query, site, limit)

    urls = _parse_google_results(html, site)
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


# ---------------------------------------------------------------------------
# DuckDuckGo fallback
# ---------------------------------------------------------------------------


async def _ddgs_fallback(query: str, site: Optional[str], limit: int) -> dict:
    def _run() -> list[str]:
        search_query = f"site:{site} {query}" if site else query
        collected: list[str] = []
        try:
            with DDGS() as ddgs:
                for result in ddgs.text(search_query, max_results=limit * 3):
                    url = result.get("href") or result.get("link")
                    if not url:
                        continue
                    if site and site.lower() not in url.lower():
                        continue
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


# ---------------------------------------------------------------------------
# Legacy sync wrapper (kept for cases/asking.py backward compatibility)
# ---------------------------------------------------------------------------


def browser(query, site=None, limit=10, scrape_lp=True):
    """Synchronous wrapper around the async SERP flow.

    Preserves the old return shape so `cases/asking.py` keeps working.
    """
    try:
        return asyncio.run(google_serp_search(query, site=site, limit=limit))
    except RuntimeError:
        # We're inside a running event loop — run in a thread.
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(
                lambda: asyncio.run(google_serp_search(query, site=site, limit=limit))
            ).result()
