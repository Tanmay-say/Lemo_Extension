import httpx
import os
from bs4 import BeautifulSoup
import re
from typing import List, Union
from scrapingbee import ScrapingBeeClient

# Initialize ScrapingBee client
SCRAPINGBEE_API_KEY = os.getenv("SCRAPINGBEE_API_KEY")
scrapingbee_client = ScrapingBeeClient(api_key=SCRAPINGBEE_API_KEY) if SCRAPINGBEE_API_KEY and SCRAPINGBEE_API_KEY != "PLACEHOLDER_GET_FROM_SCRAPINGBEE_COM" else None

async def web_scrapper(url: str, full_page: bool = False) -> Union[List[str], str]:
    """
    Advanced web scraper with ScrapingBee integration for production-grade scraping
    Falls back to httpx for simple pages
    
    Args:
        url: URL to scrape
        full_page: If True, extract detailed product information
        
    Returns:
        List of text chunks (full_page=True) or single chunk string (full_page=False)
    """
    try:
        # Check for non-scrapable URLs first
        non_scrapable_schemes = ['chrome://', 'chrome-extension://', 'about:', 'file://', 'data:', 'javascript:', 'edge://', 'brave://']
        is_non_scrapable = any(url.lower().startswith(scheme) for scheme in non_scrapable_schemes)
        
        if is_non_scrapable:
            print(f"\n{'='*80}")
            print(f"[SCRAPER] ✗ SKIPPED: Cannot scrape browser-internal URL: {url}")
            print(f"[SCRAPER] This is a {url.split(':')[0]}:// page - not a real website")
            print(f"{'='*80}\n")
            return []
        
        print(f"\n{'='*80}")
        print(f"[SCRAPER] Starting scrape for: {url}")
        print(f"{'='*80}")
        
        # Determine if we should use ScrapingBee (for e-commerce sites)
        use_scrapingbee = scrapingbee_client is not None and any(
            domain in url.lower() for domain in ['amazon', 'flipkart', 'ebay', 'walmart', 'etsy']
        )
        
        html_content = None
        
        if use_scrapingbee:
            print(f"[SCRAPER] Using ScrapingBee for enhanced scraping...")
            try:
                response = scrapingbee_client.get(
                    url,
                    params={
                        'render_js': 'true',  # Execute JavaScript
                        'premium_proxy': 'true',  # Use premium rotating proxies
                        'country_code': 'us',  # Geo-targeting
                    }
                )
                html_content = response.content.decode('utf-8')
                print(f"[SCRAPER] ✓ ScrapingBee scrape successful")
                print(f"[SCRAPER] Response Length: {len(html_content)} characters")
            except Exception as e:
                print(f"[SCRAPER] ScrapingBee failed: {e}, falling back to httpx...")
                use_scrapingbee = False
        
        # Fallback to httpx for simple scraping
        if not use_scrapingbee or html_content is None:
            print(f"[SCRAPER] Using httpx for basic scraping...")
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                html_content = response.text
                print(f"[SCRAPER] Response Status: {response.status_code}")
                print(f"[SCRAPER] Response Length: {len(html_content)} characters")
        
        # Parse HTML
        soup = BeautifulSoup(html_content, 'html.parser')

        if full_page:
            return _extract_full_page_data(soup, url)
        else:
            return _extract_simple_chunk(soup)
    
    except httpx.RequestError as e:
        print(f"[SCRAPER ERROR] HTTP request failed for {url}: {e}")
        raise
    except Exception as e:
        print(f"[SCRAPER ERROR] Unexpected error: {e}")
        raise


def _extract_full_page_data(soup: BeautifulSoup, url: str) -> List[str]:
    """Extract detailed product information from page"""
    print(f"[SCRAPER] Extracting product information...")
    
    product_data = []
    
    # Title extraction
    title_selectors = [
        {'id': 'productTitle'},
        {'class_': 'product-title'},
        {'class_': 'a-size-large'},
        {'name': 'h1'}
    ]
    for selector in title_selectors:
        title = soup.find('span', selector) or soup.find('h1', selector)
        if title:
            title_text = title.get_text(strip=True)
            if title_text and len(title_text) > 10:
                product_data.append(f"PRODUCT TITLE: {title_text}")
                print(f"[SCRAPER] ✓ Found title: {title_text[:80]}...")
                break
    
    # Price extraction (multiple strategies)
    price_found = _extract_price(soup, product_data)
    
    # Rating extraction
    rating = soup.find('span', {'class': 'a-icon-alt'})
    if rating:
        rating_text = rating.get_text(strip=True)
        product_data.append(f"RATING: {rating_text}")
        print(f"[SCRAPER] ✓ Found rating: {rating_text}")
    
    # Review count
    rating_count = soup.find('span', {'id': 'acrCustomerReviewText'})
    if rating_count:
        count_text = rating_count.get_text(strip=True)
        product_data.append(f"REVIEWS: {count_text}")
        print(f"[SCRAPER] ✓ Found review count: {count_text}")
    
    # Features
    feature_bullets = soup.find('div', {'id': 'feature-bullets'})
    if feature_bullets:
        features = feature_bullets.get_text(strip=True)[:1000]
        product_data.append(f"FEATURES: {features}")
        print(f"[SCRAPER] ✓ Found features: {features[:150]}...")
    
    # Description
    desc = soup.find('div', {'id': 'productDescription'})
    if desc:
        desc_text = desc.get_text(strip=True)[:800]
        product_data.append(f"DESCRIPTION: {desc_text}")
        print(f"[SCRAPER] ✓ Found description: {desc_text[:100]}...")
    
    # Get full page text
    full_text = soup.get_text(separator=' ', strip=True)
    
    if not full_text or len(full_text) < 100:
        print(f"[SCRAPER] ✗✗✗ CRITICAL: Minimal text extracted ({len(full_text)} chars)")
        return []
    
    print(f"[SCRAPER] ✓ Full page text: {len(full_text)} characters")
    
    # Combine product data with full text
    if product_data:
        combined_text = ' | '.join(product_data) + ' | ' + full_text
        print(f"[SCRAPER] ✓ Combined with extracted product data")
    else:
        combined_text = full_text
        print(f"[SCRAPER] ⚠ No structured data found, using raw text only")
    
    # Clean and chunk
    combined_text = ' '.join(combined_text.split())
    chunks = [combined_text[i:i+1000] for i in range(0, len(combined_text), 1000)]
    chunks = [chunk for chunk in chunks if len(chunk.strip()) > 20]
    
    print(f"[SCRAPER] ✓✓✓ SUCCESS: Created {len(chunks)} chunks")
    print(f"{'='*80}\n")
    
    return chunks


def _extract_price(soup: BeautifulSoup, product_data: List[str]) -> bool:
    """Extract price using multiple strategies"""
    # Strategy 1: Amazon-specific
    price_container = soup.find('span', {'class': 'a-price'})
    if price_container:
        whole = price_container.find('span', {'class': 'a-price-whole'})
        fraction = price_container.find('span', {'class': 'a-price-fraction'})
        symbol = price_container.find('span', {'class': 'a-price-symbol'})
        
        if whole:
            price_text = ''
            if symbol:
                price_text += symbol.get_text(strip=True)
            price_text += whole.get_text(strip=True)
            if fraction:
                price_text += fraction.get_text(strip=True)
            
            if price_text and any(char.isdigit() for char in price_text):
                product_data.append(f"PRICE: {price_text}")
                print(f"[SCRAPER] ✓ Found price: {price_text}")
                return True
    
    # Strategy 2: Generic price patterns
    price_patterns = [
        {'class': 'price'},
        {'class': 'product-price'},
        {'class': 'current-price'},
        {'id': 'priceblock_ourprice'},
    ]
    
    for pattern in price_patterns:
        price_elem = soup.find(['span', 'div', 'p'], pattern)
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            if price_text and any(char.isdigit() for char in price_text):
                product_data.append(f"PRICE: {price_text}")
                print(f"[SCRAPER] ✓ Found price: {price_text}")
                return True
    
    print(f"[SCRAPER] ✗ No price found")
    return False


def _extract_simple_chunk(soup: BeautifulSoup) -> str:
    """Extract simple text chunk from page"""
    # Extract h tags and p tags in order
    all_tags = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p'])
    
    # Build a single chunk up to 1000 characters
    chunk = ""
    for tag in all_tags:
        text = tag.get_text(strip=True)
        if text:
            if chunk:
                potential_addition = chunk + " " + text
            else:
                potential_addition = text
            
            if len(potential_addition) > 1000:
                break
            
            chunk = potential_addition
    
    return chunk if chunk else ""
