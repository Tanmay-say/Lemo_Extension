import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from helpers.web_scrapper import web_scrapper
from helpers.embedder import generate_embedding
from helpers.redis_functions import store_page_vector, get_relevant_content


async def current_page_context(url: str, query: str):
    try:
        print(f"\n{'='*80}")
        print(f"[CONTEXT] Starting context retrieval")
        print(f"[CONTEXT] URL: {url}")
        print(f"[CONTEXT] Query: {query}")
        print(f"{'='*80}\n")
        
        print("[CONTEXT] Step 1: Calling web scraper...")
        chunks = await web_scrapper(url, full_page=True)
        
        if not chunks or len(chunks) == 0:
            print("[CONTEXT] ✗✗✗ Step 1 FAILED: No chunks retrieved from webpage")
            print("[CONTEXT] Returning empty [] (will trigger fallback in asking.py)")
            return []
        
        print(f"[CONTEXT] ✓ Step 1 SUCCESS: Retrieved {len(chunks)} chunks")
        
        print(f"[CONTEXT] Step 2: Processing embeddings and storing in Redis...")
        stored_count = 0
        for i, chunk in enumerate(chunks):
            try:
                embedding = generate_embedding(chunk)
                result = store_page_vector(url, chunk, embedding)
                stored_count += 1
                if (i + 1) % 5 == 0:  # Log every 5 chunks
                    print(f"[CONTEXT] Processed {i+1}/{len(chunks)} chunks...")
            except Exception as e:
                print(f"[CONTEXT] ✗ Failed to process chunk {i+1}: {e}")
                continue
        
        print(f"[CONTEXT] ✓ Step 2 SUCCESS: Stored {stored_count}/{len(chunks)} chunks in Redis")
        
        print("[CONTEXT] Step 3: Generating query embedding...")
        query_embedding = generate_embedding(query)
        print("[CONTEXT] ✓ Step 3 SUCCESS: Query embedding generated")
        
        print("[CONTEXT] Step 4: Searching Redis for relevant content...")
        content = get_relevant_content(url, query_embedding, top_k=5)
        
        if content and len(content) > 0:
            print(f"[CONTEXT] ✓✓✓ Step 4 SUCCESS: Found {len(content)} relevant chunks")
            print(f"[CONTEXT] First chunk preview: {content[0][:150] if content[0] else 'empty'}...")
        else:
            print(f"[CONTEXT] ✗ Step 4 WARNING: No relevant content found in Redis")
        
        print(f"{'='*80}\n")
        return content
    
    except Exception as e:
        print(f"[ERROR] Error in current_page_context: {e}")
        import traceback
        traceback.print_exc()
        return []


if __name__ == "__main__":
    print("[INFO] Running current_page_context test")
    content = current_page_context("https://allensolly.abfrl.in/p/men-blue-textured-polo-neck-t-shirt-39871258.html", "What is this product about?")
    print("[RESULT] Relevant content:")
    print(content)