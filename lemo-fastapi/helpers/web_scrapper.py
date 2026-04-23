"""Web scraper — production-grade product-page extractor.

Strategy (in order of preference for each field)
------------------------------------------------
1. JSON-LD `@type=Product` block          -> works on Flipkart, Myntra, Meesho,
                                             many Shopify stores, etc.
2. Platform-specific DOM selectors        -> Amazon, Flipkart.
3. Generic fallbacks                      -> og:title, <title>, <h1>, meta
                                             price, and a last-resort `₹`/`$`
                                             regex sweep.

The new extractor is driven by this cascade so a single page that fails one
strategy still yields a title + price instead of an empty chunk list. The old
extractor was Amazon-only which is why Flipkart pages came back with
`title=''` and got dropped by the rapidfuzz filter.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import Any, List, Optional, Union
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from scrapingbee import ScrapingBeeClient

logger = logging.getLogger(__name__)


SCRAPINGBEE_API_KEY = (os.getenv("SCRAPINGBEE_API_KEY") or "").strip()
if SCRAPINGBEE_API_KEY.startswith("PLACEHOLDER"):
    SCRAPINGBEE_API_KEY = ""

scrapingbee_client: Optional[ScrapingBeeClient] = (
    ScrapingBeeClient(api_key=SCRAPINGBEE_API_KEY) if SCRAPINGBEE_API_KEY else None
)


_SPA_HOSTS = ("flipkart.com", "myntra.com", "ajio.com", "nykaa.com", "meesho.com")
_ECOM_HOSTS = ("amazon", "flipkart", "ebay", "walmart", "etsy", "myntra", "ajio", "nykaa", "meesho")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def web_scrapper(url: str, full_page: bool = False) -> Union[List[str], str]:
    """Return a list of text chunks (full_page=True) or a single chunk string.

    Uses ScrapingBee for e-commerce domains, httpx otherwise. Raises on
    unrecoverable errors so callers (scraper_agent) can mark the candidate dead.
    """
    non_scrapable_schemes = (
        "chrome://", "chrome-extension://", "about:", "file://",
        "data:", "javascript:", "edge://", "brave://",
    )
    if any(url.lower().startswith(s) for s in non_scrapable_schemes):
        logger.info("[scraper] skipped non-scrapable scheme: %s", url[:80])
        return []

    logger.info("[scraper] fetch %s", url[:160])

    host = urlparse(url).netloc.lower()
    country_code = "in" if host.endswith(".in") or "flipkart" in host else "us"
    needs_js = any(spa in host for spa in _SPA_HOSTS)

    html_content = await _fetch_html(url, host, country_code, needs_js)
    if not html_content:
        return []

    soup = BeautifulSoup(html_content, "html.parser")

    if full_page:
        return _extract_full_page_data(soup, url)
    return _extract_simple_chunk(soup)


async def _fetch_html(
    url: str, host: str, country_code: str, needs_js: bool
) -> Optional[str]:
    use_scrapingbee = scrapingbee_client is not None and any(d in host for d in _ECOM_HOSTS)

    if use_scrapingbee:
        try:
            params: dict[str, Any] = {
                "render_js": "true" if needs_js else "false",
                "premium_proxy": "true",
                "country_code": country_code,
                # ScrapingBee accepts `timeout` in milliseconds (max 140000).
                "timeout": "35000",
            }
            if needs_js:
                # Give SPAs a few seconds to hydrate before snapshotting the DOM.
                params["wait"] = "2500"

            # Defensive wall-clock guard so a hung ScrapingBee request can't
            # freeze the whole pipeline. 40s is already generous.
            response = await asyncio.wait_for(
                asyncio.to_thread(scrapingbee_client.get, url, params=params),
                timeout=40.0,
            )
            html_content = response.content.decode("utf-8", errors="ignore")
            logger.info(
                "[scraper] scrapingbee ok render_js=%s country=%s bytes=%d",
                params["render_js"], country_code, len(html_content),
            )
            return html_content
        except asyncio.TimeoutError:
            logger.warning("[scraper] scrapingbee timeout (>40s) — falling back to httpx")
        except Exception as exc:
            logger.warning("[scraper] scrapingbee failed (%s) — falling back to httpx", exc)

    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            response = await asyncio.wait_for(
                client.get(url, headers=headers), timeout=25.0
            )
            response.raise_for_status()
            html_content = response.text
            logger.info(
                "[scraper] httpx ok status=%s bytes=%d",
                response.status_code, len(html_content),
            )
            return html_content
    except asyncio.TimeoutError:
        logger.warning("[scraper] httpx fetch timed out after 25s")
        return None
    except Exception as exc:
        logger.warning("[scraper] httpx fetch failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# JSON-LD helpers
# ---------------------------------------------------------------------------


def _iter_ld_products(soup: BeautifulSoup) -> list[dict]:
    """Yield each Product object found in <script type='application/ld+json'>."""
    products: list[dict] = []
    for tag in soup.find_all("script", {"type": "application/ld+json"}):
        raw = tag.string or tag.get_text() or ""
        if not raw.strip():
            continue
        try:
            data: Any = json.loads(raw)
        except Exception:
            continue
        for node in _walk_ld(data):
            if isinstance(node, dict) and _ld_type(node) in {"Product", "ProductModel", "IndividualProduct"}:
                products.append(node)
    return products


def _walk_ld(node: Any):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk_ld(v)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_ld(item)


def _ld_type(node: dict) -> str:
    t = node.get("@type")
    if isinstance(t, list) and t:
        t = t[0]
    return str(t or "")


def _ld_price(product: dict) -> Optional[str]:
    offers = product.get("offers")
    if not offers:
        return None
    if isinstance(offers, list):
        offers = offers[0]
    if not isinstance(offers, dict):
        return None
    price = offers.get("price") or offers.get("lowPrice") or offers.get("highPrice")
    currency = offers.get("priceCurrency") or offers.get("currency")
    if price is None:
        return None
    price_str = str(price).strip()
    if not price_str:
        return None
    if currency and currency.upper() == "INR":
        return f"₹{price_str}"
    if currency and currency.upper() in {"USD", "US$"}:
        return f"${price_str}"
    if currency:
        return f"{price_str} {currency}"
    return price_str


def _ld_rating(product: dict) -> tuple[Optional[str], Optional[str]]:
    agg = product.get("aggregateRating")
    if not isinstance(agg, dict):
        return None, None
    value = agg.get("ratingValue") or agg.get("ratingvalue")
    count = agg.get("reviewCount") or agg.get("ratingCount")
    return (
        f"{value} out of 5 stars" if value is not None else None,
        f"({count})" if count is not None else None,
    )


# ---------------------------------------------------------------------------
# Text heuristics
# ---------------------------------------------------------------------------


_TITLE_SUFFIXES = re.compile(
    r"""\s*(?:\|\s*)?(?:
        Online\s+(?:at|Shopping|Store).*|
        Buy\s+Online.*|
        Free\s+Shipping.*|
        \-\s*Amazon\.(?:in|com).*|
        \-\s*Flipkart\.com.*|
        at\s+Best\s+Price.*
    )\s*$""",
    re.IGNORECASE | re.VERBOSE,
)


def _clean_title(raw: str) -> str:
    if not raw:
        return ""
    cleaned = " ".join(raw.split())
    cleaned = _TITLE_SUFFIXES.sub("", cleaned).strip(" -|")
    return cleaned[:280]


_PRICE_RE = re.compile(
    r"(?:₹|Rs\.?\s?|INR\s?|\$|US\$|USD\s?)\s?([\d]{1,3}(?:[,\d]{0,12}))(?:\.\d{1,2})?"
)


def _biggest_currency_amount(html_or_text: str, prefer_inr: bool) -> Optional[str]:
    """Find the largest currency amount in a blob. Used as a last-resort price."""
    best_value = -1
    best_match = None
    for m in _PRICE_RE.finditer(html_or_text):
        amount_raw = m.group(1)
        try:
            amount = int(amount_raw.replace(",", ""))
        except ValueError:
            continue
        if amount < 50 or amount > 50_000_000:  # sanity filter
            continue
        prefix = m.group(0).lstrip().split()[0]
        if prefer_inr and not prefix.startswith(("₹", "Rs", "INR")):
            continue
        if amount > best_value:
            best_value = amount
            best_match = m.group(0).strip()
    return best_match


# ---------------------------------------------------------------------------
# Platform-specific DOM selectors
# ---------------------------------------------------------------------------


def _amazon_fields(soup: BeautifulSoup) -> dict:
    out: dict[str, str] = {}
    title_el = soup.find("span", id="productTitle") or soup.find("h1", id="title")
    if title_el:
        out["title"] = _clean_title(title_el.get_text(strip=True))

    price_container = soup.find("span", {"class": "a-price"})
    if price_container:
        whole = price_container.find("span", {"class": "a-price-whole"})
        frac = price_container.find("span", {"class": "a-price-fraction"})
        sym = price_container.find("span", {"class": "a-price-symbol"})
        if whole:
            parts = [x.get_text(strip=True) for x in (sym, whole, frac) if x]
            if parts:
                out["price"] = "".join(parts)

    rating = soup.find("span", {"class": "a-icon-alt"})
    if rating:
        out["rating"] = rating.get_text(strip=True)

    review_count = soup.find("span", {"id": "acrCustomerReviewText"})
    if review_count:
        out["reviews"] = review_count.get_text(strip=True)

    feature_bullets = soup.find("div", {"id": "feature-bullets"})
    if feature_bullets:
        out["features"] = feature_bullets.get_text(" ", strip=True)[:1000]

    desc = soup.find("div", {"id": "productDescription"})
    if desc:
        out["description"] = desc.get_text(" ", strip=True)[:800]
    return out


def _flipkart_fields(soup: BeautifulSoup) -> dict:
    out: dict[str, str] = {}
    h1 = soup.find("h1")
    if h1:
        out["title"] = _clean_title(h1.get_text(" ", strip=True))

    # Flipkart rotates hashed classnames, but its selling-price node carries an
    # aria-like structure starting with ₹. Grab the largest INR number.
    biggest = _biggest_currency_amount(str(soup)[:250_000], prefer_inr=True)
    if biggest:
        out["price"] = biggest

    return out


def _generic_fields(soup: BeautifulSoup) -> dict:
    out: dict[str, str] = {}

    og_title = soup.find("meta", {"property": "og:title"})
    if og_title and og_title.get("content"):
        out["title"] = _clean_title(og_title["content"])

    if not out.get("title"):
        title_tag = soup.find("title")
        if title_tag and title_tag.get_text(strip=True):
            out["title"] = _clean_title(title_tag.get_text(strip=True))

    og_desc = soup.find("meta", {"property": "og:description"}) or soup.find(
        "meta", {"name": "description"}
    )
    if og_desc and og_desc.get("content"):
        out["description"] = og_desc["content"][:800]

    price_meta = soup.find("meta", {"property": "product:price:amount"}) or soup.find(
        "meta", {"itemprop": "price"}
    )
    currency_meta = soup.find("meta", {"property": "product:price:currency"}) or soup.find(
        "meta", {"itemprop": "priceCurrency"}
    )
    if price_meta and price_meta.get("content"):
        p = price_meta["content"].strip()
        c = (currency_meta.get("content") if currency_meta else "").strip() if currency_meta else ""
        if c.upper() == "INR":
            out["price"] = f"₹{p}"
        elif c.upper() in {"USD", "US$"}:
            out["price"] = f"${p}"
        else:
            out["price"] = f"{p} {c}".strip()
    return out


# ---------------------------------------------------------------------------
# Extraction — full page
# ---------------------------------------------------------------------------


def _extract_full_page_data(soup: BeautifulSoup, url: str) -> List[str]:
    host = urlparse(url).netloc.lower()
    product_data: list[str] = []

    merged: dict[str, str] = {}

    # 1. JSON-LD wins when present — most accurate, but not always there.
    ld_products = _iter_ld_products(soup)
    if ld_products:
        p = ld_products[0]
        name = p.get("name")
        if name:
            merged["title"] = _clean_title(str(name))
        price = _ld_price(p)
        if price:
            merged["price"] = price
        rating, reviews = _ld_rating(p)
        if rating:
            merged["rating"] = rating
        if reviews:
            merged["reviews"] = reviews
        desc = p.get("description")
        if desc:
            merged["description"] = str(desc)[:800]
        brand = p.get("brand")
        if isinstance(brand, dict):
            brand = brand.get("name")
        if brand:
            merged["brand"] = str(brand)[:120]

    # 2. Platform-specific DOM.
    if "amazon" in host:
        for k, v in _amazon_fields(soup).items():
            merged.setdefault(k, v)
    elif "flipkart" in host:
        for k, v in _flipkart_fields(soup).items():
            merged.setdefault(k, v)

    # 3. Generic OG / title / meta price fallback for any field still missing.
    for k, v in _generic_fields(soup).items():
        merged.setdefault(k, v)

    # 4. Last-resort: biggest currency amount anywhere in HTML.
    if "price" not in merged:
        prefer_inr = host.endswith(".in") or "flipkart" in host
        biggest = _biggest_currency_amount(str(soup)[:250_000], prefer_inr=prefer_inr)
        if biggest:
            merged["price"] = biggest

    # Stitch into the `LABEL: value | LABEL: value | ...` chunk format that
    # `agents.scraper_agent._payload_from_chunks` already parses.
    field_order = ("title", "price", "rating", "reviews", "brand", "features", "description")
    label_by_field = {
        "title": "PRODUCT TITLE",
        "price": "PRICE",
        "rating": "RATING",
        "reviews": "REVIEWS",
        "brand": "BRAND",
        "features": "FEATURES",
        "description": "DESCRIPTION",
    }
    for field in field_order:
        val = merged.get(field)
        if val:
            product_data.append(f"{label_by_field[field]}: {val}")

    if merged.get("title"):
        logger.info("[scraper] extracted title=%r price=%s", merged["title"][:80], merged.get("price"))
    else:
        logger.info("[scraper] title missing — will rely on URL slug in agent")

    full_text = soup.get_text(separator=" ", strip=True)
    if not full_text or len(full_text) < 100:
        logger.warning("[scraper] minimal text extracted (%d chars)", len(full_text))
        return product_data[:]  # at least return whatever structured info we have

    combined = (" | ".join(product_data) + " | " + full_text) if product_data else full_text
    combined = " ".join(combined.split())

    chunks = [combined[i:i + 1000] for i in range(0, len(combined), 1000)]
    chunks = [c for c in chunks if len(c.strip()) > 20]

    logger.info("[scraper] SUCCESS %d chunks, structured fields: %s",
                len(chunks), [f for f in field_order if f in merged])
    return chunks


def _extract_simple_chunk(soup: BeautifulSoup) -> str:
    all_tags = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p"])
    chunk = ""
    for tag in all_tags:
        text = tag.get_text(strip=True)
        if not text:
            continue
        candidate = (chunk + " " + text) if chunk else text
        if len(candidate) > 1000:
            break
        chunk = candidate
    return chunk
