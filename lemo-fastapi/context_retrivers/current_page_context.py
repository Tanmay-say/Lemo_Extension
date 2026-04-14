import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from helpers.embedder import generate_embedding
from helpers.redis_functions import get_relevant_content, store_page_vector
from helpers.web_scrapper import web_scrapper


async def current_page_context(url: str, query: str):
    try:
        print(f"\n{'=' * 80}")
        print("[CONTEXT] Starting context retrieval")
        print(f"[CONTEXT] URL: {url}")
        print(f"[CONTEXT] Query: {query}")
        print(f"{'=' * 80}\n")

        print("[CONTEXT] Step 1: Calling web scraper...")
        chunks = await web_scrapper(url, full_page=True)

        if not chunks:
            print("[CONTEXT] Step 1 FAILED: No chunks retrieved from webpage")
            print("[CONTEXT] Returning empty [] (will trigger fallback in asking.py)")
            return []

        print(f"[CONTEXT] Step 1 SUCCESS: Retrieved {len(chunks)} chunks")

        print("[CONTEXT] Step 2: Processing embeddings and storing in Redis...")
        stored_count = 0
        for index, chunk in enumerate(chunks, start=1):
            try:
                embedding = generate_embedding(chunk)
                await store_page_vector(url, chunk, embedding)
                stored_count += 1
                if index % 5 == 0:
                    print(f"[CONTEXT] Processed {index}/{len(chunks)} chunks...")
            except Exception as exc:
                print(f"[CONTEXT] Failed to process chunk {index}: {exc}")

        print(f"[CONTEXT] Step 2 SUCCESS: Stored {stored_count}/{len(chunks)} chunks in Redis")

        print("[CONTEXT] Step 3: Generating query embedding...")
        query_embedding = generate_embedding(query)
        print("[CONTEXT] Step 3 SUCCESS: Query embedding generated")

        print("[CONTEXT] Step 4: Searching Redis for relevant content...")
        content = await get_relevant_content(url, query_embedding, top_k=5)

        # The first scraped chunk contains the scraper's structured product
        # summary. Always keep it in the returned context.
        first_chunk = chunks[0]
        content_strings = [item[0] if isinstance(item, tuple) else item for item in (content or [])]
        if first_chunk not in content_strings:
            content = [(first_chunk, 1.0)] + (content or [])
            content = content[:5]

        if content:
            print(f"[CONTEXT] Step 4 SUCCESS: Found {len(content)} relevant chunks")
            preview = content[0][0] if isinstance(content[0], tuple) else content[0]
            print(f"[CONTEXT] First chunk preview: {preview[:150] if preview else 'empty'}...")
        else:
            print("[CONTEXT] Step 4 WARNING: No relevant content found in Redis")

        print(f"{'=' * 80}\n")
        return content

    except Exception as exc:
        print(f"[ERROR] Error in current_page_context: {exc}")
        import traceback

        traceback.print_exc()
        return []


if __name__ == "__main__":
    print("[INFO] Running current_page_context test")
    content = current_page_context(
        "https://allensolly.abfrl.in/p/men-blue-textured-polo-neck-t-shirt-39871258.html",
        "What is this product about?",
    )
    print("[RESULT] Relevant content:")
    print(content)
