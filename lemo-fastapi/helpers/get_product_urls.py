import httpx
from bs4 import BeautifulSoup
from ddgs import DDGS
from urllib.parse import urljoin

SITE_PATTERNS = {
    'myntra.com': {'sp_check': lambda url: '/buy' in url},
    'ajio.com': {'sp_check': lambda url: '/p/' in url},
    'nykaafashion.com': {'sp_check': lambda url: '/p/' in url},
    'amazon.in': {'sp_check': lambda url: '/dp/' in url},
    'flipkart.com': {'sp_check': lambda url: '/p/' in url},
    'allensolly.abfrl.in': {'sp_check': lambda url: '/p/' in url}

    # Add more sites here
}

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
    product_links = set()
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = httpx.get(list_page_url, headers=headers, timeout=10.0)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        all_links = soup.find_all('a', href=True)
        for link in all_links:
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

def browser(query, site=None, limit=10, scrape_lp=True):
    if site:
        search_query = f"site:{site} {query}"
    else:
        search_query = query

    all_urls = []
    try:
        with DDGS() as ddgs:
            results = ddgs.text(search_query, max_results=limit * 3)
            for result in results:
                url = result.get('href') or result.get('link')
                if url:
                    if site:
                        if site.lower() in url.lower():
                            all_urls.append(url)
                    else:
                        all_urls.append(url)
    except Exception:
        return {"success": False, "message": "Error during search", "urls": []}

    product_pages, list_pages = categorize_urls(all_urls, site)

    if len(product_pages) < limit and scrape_lp and list_pages:
        scraped_products = set(product_pages)
        for lp_url in list_pages:
            if len(scraped_products) >= limit:
                break
            new_products = scrape_product_links(lp_url, site, max_links=limit - len(scraped_products))
            if new_products:
                scraped_products.update(new_products)
        product_pages = list(scraped_products)[:limit]

    return {
        "success": True if product_pages else False,
        "message": "URLs fetched successfully" if product_pages else "No product URLs found",
        "urls": list(product_pages)[:limit]
    }