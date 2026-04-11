import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from helpers.get_product_urls import browser
from helpers.web_scrapper import web_scrapper
from helpers.embedder import generate_embedding
from helpers.redis_functions import store_vector, search_similar, create_redis_index


async def product_recommendation(domain: str, user_query: str):
    print(f"[LOG] Starting product recommendation for query: '{user_query}' on domain: '{domain}'")
    
    # Ensure Redis index exists before storing/searching
    try:
        create_redis_index()
    except Exception as e:
        print(f"[ERROR] Failed to create/verify Redis index: {e}")
        return set()
    
    # Fetch product URLs
    try:
        browser_result = browser(user_query, domain, 10)
        if not browser_result.get("success") or not browser_result.get("urls"):
            print(f"[WARNING] No products found from browser")
            list_of_products = []
        else:
            list_of_products = browser_result["urls"]
        print(f"[LOG] Found {len(list_of_products)} products from browser")
    except Exception as e:
        print(f"[ERROR] Browser search failed: {e}")
        return set()
    
    # Process and store products
    for idx, product_url in enumerate(list_of_products, 1):
        print(f"[LOG] Processing product {idx}/{len(list_of_products)}: {product_url}")
        try:
            chunk = await web_scrapper(product_url)
            print(f"[LOG] Extracted chunk from {product_url}")
            
            if not chunk or (isinstance(chunk, str) and len(chunk.strip()) == 0):
                print(f"[WARNING] Empty chunk extracted from {product_url}, skipping")
                continue
            
            print(f"[LOG] Generating embedding for chunk")
            embedding = generate_embedding(product_url + " " + chunk)
            print(f"[LOG] Storing vector for {product_url}")
            result = store_vector(product_url, embedding)
            if result.get("status") != "success":
                print(f"[WARNING] Failed to store vector: {result.get('message')}")
        except Exception as e:
            print(f"[ERROR] Failed to process {product_url}: {e}")
            continue
    
    # Search for similar products
    try:
        print(f"[LOG] Generating embedding for user query: '{user_query}'")
        query_embedding = generate_embedding(user_query)
        
        # Note: Requesting top 10 but only stored 4 new products
        # This may return old/unrelated products from Redis if they exist
        print(f"[LOG] Searching for similar products (top 10)")
        similar_products = search_similar(query_embedding, 10)
        print(f"[LOG] Found {len(similar_products)} similar products")
        
        # Use generator expression instead of list comprehension in set()
        similar_products_urls = {product[0] for product in similar_products}
        print(f"[LOG] Unique product URLs: {len(similar_products_urls)}")
        print(f"[LOG] Recommendation complete. Returning {len(similar_products_urls)} unique products")
        
        return similar_products_urls
    except Exception as e:
        print(f"[ERROR] Failed to search for similar products: {e}")
        return set()


# if __name__ == "__main__":
#     result = product_recommendation("allensolly.abfrl.in", "Blue Jeans for men")
#     print(result)