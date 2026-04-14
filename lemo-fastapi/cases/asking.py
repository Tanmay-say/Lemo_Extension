from context_retrivers.current_page_context import current_page_context
from context_retrivers.product_recommendation import product_recommendation
from langchain_core.messages import HumanMessage, SystemMessage
from prompts.currentpage_asking import currentpage_asking_prompt
from prompts.product_recommendation_prompt import product_recommendation_prompt
from prompts.chat_history_responce_prompt import chat_history_response_prompt
from helpers.llm_config import LLMConfigurationError, LLMServiceUnavailableError, get_llm_for_task, invoke_llm_with_fallback, normalize_llm_exception
import re


def _get_asking_llm():
    return get_llm_for_task("general")


def _extract_field(label: str, context_text: str) -> str | None:
    match = re.search(rf"{label}:\s*(.+?)(?:\s+\|\s+|$)", context_text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    value = " ".join(match.group(1).split())
    return value[:300] if value else None


def _looks_like_structured_product_context(context_text: str) -> bool:
    return any(
        token in context_text
        for token in ("PRODUCT TITLE:", "PRICE:", "RATING:", "REVIEWS:", "FEATURES:", "DESCRIPTION:")
    )


async def _get_structured_product_context(current_page_url: str, context_text: str) -> str:
    if _looks_like_structured_product_context(context_text):
        return context_text

    try:
        from helpers.web_scrapper import web_scrapper

        direct_chunks = await web_scrapper(current_page_url, full_page=True)
        if direct_chunks:
            return "\n".join(direct_chunks[:3])
    except Exception as scrape_error:
        print(f"[ASKING] Structured fallback scrape failed: {scrape_error}")

    return context_text


def _fallback_current_page_answer(user_query: str, current_page_url: str, context_text: str) -> str:
    title = _extract_field("PRODUCT TITLE", context_text)
    price = _extract_field("PRICE", context_text)
    rating = _extract_field("RATING", context_text)
    reviews = _extract_field("REVIEWS", context_text)
    features = _extract_field("FEATURES", context_text)
    description = _extract_field("DESCRIPTION", context_text)

    lines = ["Here is the product summary I could extract from the page:"]
    if title:
        lines.append(f"Product: {title}")
    if price:
        lines.append(f"Price: {price}")
    if rating:
        lines.append(f"Rating: {rating}")
    if reviews:
        lines.append(f"Reviews: {reviews}")
    if features:
        lines.append(f"Highlights: {features[:500]}")
    elif description:
        lines.append(f"Description: {description[:500]}")
    elif current_page_url:
        domain_match = re.search(r"https?://([^/]+)", current_page_url, flags=re.IGNORECASE)
        if domain_match:
            lines.append(f"Source: {domain_match.group(1)}")

    if not any((title, price, rating, reviews, features, description)):
        lines.append("I could not generate a conversational answer because the LLM providers are unavailable.")
    return "\n".join(lines)


async def current_page_asking(user_query: str, current_page_url: str):
    try:
        print(f"\n{'='*80}")
        print(f"[ASKING] Processing query: {user_query}")
        print(f"[ASKING] Current URL: {current_page_url}")
        print(f"{'='*80}\n")
        
        # Check if it's a browser-internal page
        non_scrapable_schemes = ['chrome://', 'chrome-extension://', 'about:', 'file://', 'data:', 'javascript:', 'edge://', 'brave://']
        is_non_scrapable = any(current_page_url.lower().startswith(scheme) for scheme in non_scrapable_schemes)
        
        if is_non_scrapable:
            print(f"[ASKING] ✗ Browser-internal page detected: {current_page_url}")
            print(f"[ASKING] Returning helpful message to user")
            return (
                "I can't analyze browser-internal pages like new tabs or extension pages. "
                "Please navigate to an e-commerce product page (Amazon, Flipkart, etc.) "
                "and I'll be happy to help you analyze the product! 🛍️"
            )
        
        # TRY METHOD 1: Vector embeddings with Redis
        print(f"[ASKING] Attempting Method 1: Vector embeddings...")
        context = await current_page_context(current_page_url, user_query)
        
        # Handle different context types
        if isinstance(context, list) and len(context) > 0:
            # Extract only the content from tuples (content, score)
            context_strings = [item[0] if isinstance(item, tuple) else item for item in context]
            context_text = "\n".join(context_strings)
            print(f"[ASKING] ✓✓✓ Method 1 SUCCESS: Using {len(context_strings)} embedding chunks")
        elif isinstance(context, list) and len(context) == 0:
            # METHOD 2: Direct scraping fallback
            print(f"[ASKING] ✗ Method 1 FAILED: No embeddings found")
            print(f"[ASKING] Attempting Method 2: Direct scraping fallback...")
            
            try:
                from helpers.web_scrapper import web_scrapper
                direct_chunks = await web_scrapper(current_page_url, full_page=True)
                
                if direct_chunks and len(direct_chunks) > 0:
                    # Use first 5 chunks for analysis
                    context_text = "\n\n".join(direct_chunks[:5])
                    print(f"[ASKING] ✓✓✓ Method 2 SUCCESS: Using {min(5, len(direct_chunks))} direct chunks ({len(context_text)} chars)")
                else:
                    print(f"[ASKING] ✗✗✗ Method 2 FAILED: Could not scrape page")
                    context_text = "ERROR: Unable to extract any information from this page. The page may be blocking automated access."
            except Exception as scrape_error:
                print(f"[ASKING] ✗✗✗ Method 2 CRITICAL ERROR: {scrape_error}")
                import traceback
                traceback.print_exc()
                context_text = f"ERROR: Failed to access page content due to: {str(scrape_error)}"
        else:
            context_text = str(context) if context else "No context available."
            print(f"[ASKING] ⚠ Unexpected context type: {type(context)}")
        
        print(f"[ASKING] Building prompt with context length: {len(context_text)} characters")
        print(f"[ASKING] Context preview: {context_text[:300]}...")
        
        prompt = currentpage_asking_prompt(context_text)
        messages = [SystemMessage(content=prompt), HumanMessage(content=user_query)]
        
        print(f"[ASKING] Sending to LLM provider...")
        try:
            response = await invoke_llm_with_fallback(messages, "general")
        except Exception as llm_error:
            normalized = normalize_llm_exception(llm_error)
            if isinstance(normalized, (LLMConfigurationError, LLMServiceUnavailableError)):
                print(f"[ASKING] LLM unavailable, using deterministic fallback: {normalized}")
                structured_context = await _get_structured_product_context(current_page_url, context_text)
                return _fallback_current_page_answer(user_query, current_page_url, structured_context)
            raise normalized
        
        answer = response.content if response and response.content else "I couldn't generate a response. Please try again."
        print(f"[ASKING] ✓✓✓ AI Response received: {len(answer)} characters")
        print(f"[ASKING] Response preview: {answer[:200]}...")
        print(f"{'='*80}\n")
        
        return answer
    
    except Exception as e:
        normalized = normalize_llm_exception(e)
        if normalized is not e:
            raise normalized
        print(f"[ERROR] Error in current_page_asking: {e}")
        import traceback
        traceback.print_exc()
        return "I encountered an error while processing your question. Please try again."


async def product_asking(user_query: str, domain: str):
    try:
        print(f"[LOG] product_asking called with domain: {domain}")
        recommendations = await product_recommendation(domain, user_query)
        print(f"[LOG] Got {len(recommendations) if isinstance(recommendations, (list, set)) else 'unknown'} product recommendations")
        
        prompt = product_recommendation_prompt(user_query, recommendations)
        messages = [SystemMessage(content=prompt), HumanMessage(content=user_query)]
        try:
            response = await invoke_llm_with_fallback(messages, "general")
        except Exception as llm_error:
            normalized = normalize_llm_exception(llm_error)
            if isinstance(normalized, (LLMConfigurationError, LLMServiceUnavailableError)):
                return (
                    "I could not reach an LLM provider. "
                    f"I did complete product retrieval for domain '{domain}', but I cannot generate a recommendation summary right now."
                )
            raise normalized
        
        answer = response.content if response and response.content else "I couldn't generate a response. Please try again."
        print(f"[LOG] Generated answer: {answer[:100]}...")
        return answer
    
    except Exception as e:
        normalized = normalize_llm_exception(e)
        if normalized is not e:
            raise normalized
        print(f"[ERROR] Error in product_asking: {e}")
        import traceback
        traceback.print_exc()
        return "I encountered an error while processing your product question. Please try again."


async def chat_history_asking(user_query: str, chat_history: str):
    try:
        prompt = chat_history_response_prompt(user_query, chat_history)
        messages = [SystemMessage(content=prompt), HumanMessage(content=user_query)]
        try:
            response = await invoke_llm_with_fallback(messages, "general")
        except Exception as llm_error:
            normalized = normalize_llm_exception(llm_error)
            if isinstance(normalized, (LLMConfigurationError, LLMServiceUnavailableError)):
                return (
                    "I could not reach an LLM provider, so I cannot summarize prior chat history right now."
                )
            raise normalized
        answer = response.content if response and response.content else "I couldn't generate a response. Please try again."
        print(f"[LOG] Generated answer: {answer[:100]}...")
        return answer
    except Exception as e:
        normalized = normalize_llm_exception(e)
        if normalized is not e:
            raise normalized
        print(f"[ERROR] Error in chat_history_asking: {e}")
        import traceback
        traceback.print_exc()
        return "I encountered an error while processing your chat history question. Please try again."


async def asking(user_query: str, domain: str, current_page_url: str, scope: str, session_id: str, chat_history: str):
    print(f"[LOG] asking() called with scope: {scope}")
    
    if scope == "current_page":
        return await current_page_asking(user_query, current_page_url)
    elif scope == "product":
        print(f"[LOG] Product scope detected, using product_asking")
        return await product_asking(user_query, domain)
    elif scope == "chat_history":
        # BUG FIX: pass chat_history (formatted text), NOT session_id
        return await chat_history_asking(user_query, chat_history)
    else:
        print(f"[WARNING] Unknown scope: {scope}, using current_page_asking as fallback")
        return await current_page_asking(user_query, current_page_url)
