from context_retrivers.current_page_context import current_page_context
from context_retrivers.product_recommendation import product_recommendation
from langchain_core.messages import HumanMessage, SystemMessage
from prompts.currentpage_asking import currentpage_asking_prompt
from prompts.product_recommendation_prompt import product_recommendation_prompt
from prompts.chat_history_responce_prompt import chat_history_response_prompt
from helpers.get_product_urls import browser
from helpers.llm_config import (
    LLMConfigurationError,
    LLMServiceUnavailableError,
    get_llm_for_task,
    invoke_llm_with_fallback,
    normalize_llm_exception,
)
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


def _is_compare_query(user_query: str) -> bool:
    query = (user_query or "").lower()
    return (
        "compare" in query
        or "flipkart" in query
        or "amazon" in query
        or "different platform" in query
        or "other site" in query
    )


def _normalize_price(raw_price: str | None) -> str | None:
    if not raw_price:
        return None
    cleaned = " ".join(raw_price.split())
    if cleaned.startswith(("₹", "$")):
        return cleaned
    if re.search(r"\d", cleaned):
        return f"₹{cleaned}"
    return cleaned


def _extract_numeric_rating(raw_rating: str | None) -> str | None:
    if not raw_rating:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)", raw_rating)
    return match.group(1) if match else raw_rating


def _extract_model_hint(text: str) -> str | None:
    if not text:
        return None
    candidates = re.findall(r"\b[A-Z0-9]{6,}\b", text.upper())
    return candidates[0] if candidates else None


def _product_payload_from_context(current_page_url: str, context_text: str) -> dict | None:
    title = _extract_field("PRODUCT TITLE", context_text)
    price = _normalize_price(_extract_field("PRICE", context_text))
    rating_raw = _extract_field("RATING", context_text)
    reviews = _extract_field("REVIEWS", context_text)
    features = _extract_field("FEATURES", context_text)
    description = _extract_field("DESCRIPTION", context_text)

    if not any((title, price, rating_raw, reviews, features, description)):
        return None

    return {
        "title": title or "Current product",
        "price": price or "",
        "rating": _extract_numeric_rating(rating_raw) or "",
        "rating_text": rating_raw or "",
        "reviewCount": reviews or "",
        "description": (description or features or "")[:500],
        "features": (features or "")[:800],
        "url": current_page_url,
        "image": "",
    }


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


async def compare_current_product(user_query: str, current_page_url: str, context_text: str) -> dict:
    current_product = _product_payload_from_context(current_page_url, context_text) or {
        "title": "Current product",
        "url": current_page_url,
        "price": "",
        "rating": "",
        "rating_text": "",
        "reviewCount": "",
        "description": "",
        "features": "",
        "image": "",
    }
    title = current_product.get("title") or ""
    model_hint = _extract_model_hint(title) or _extract_model_hint(context_text) or ""
    search_query = " ".join(part for part in (title, model_hint) if part).strip() or user_query.strip()

    requested_platforms = []
    lowered_query = user_query.lower()
    if "amazon" in lowered_query:
        requested_platforms.append(("Amazon", "amazon.in"))
    if "flipkart" in lowered_query:
        requested_platforms.append(("Flipkart", "flipkart.com"))
    if not requested_platforms:
        requested_platforms = [("Amazon", "amazon.in"), ("Flipkart", "flipkart.com")]

    comparison_products = []

    for platform_name, site in requested_platforms:
        candidate_url = None
        if site in current_page_url:
            candidate_url = current_page_url
        else:
            try:
                search_result = browser(search_query, site=site, limit=3)
                urls = search_result.get("urls", []) if isinstance(search_result, dict) else []
                candidate_url = urls[0] if urls else None
            except Exception as search_error:
                print(f"[COMPARE] Search failed for {site}: {search_error}")

        product_payload = None
        if candidate_url == current_page_url:
            product_payload = dict(current_product)
        elif candidate_url:
            try:
                from helpers.web_scrapper import web_scrapper

                chunks = await web_scrapper(candidate_url, full_page=True)
                compare_context = "\n".join(chunks[:3]) if chunks else ""
                product_payload = _product_payload_from_context(candidate_url, compare_context)
            except Exception as scrape_error:
                print(f"[COMPARE] Failed to scrape comparison product for {site}: {scrape_error}")

        if not product_payload and candidate_url:
            product_payload = {
                "title": title or f"{platform_name} listing",
                "price": "",
                "rating": "",
                "rating_text": "",
                "reviewCount": "",
                "description": "",
                "features": "",
                "url": candidate_url,
                "image": "",
            }

        if product_payload:
            product_payload["platform"] = platform_name
            comparison_products.append(product_payload)

    lines = [f"Here is a cross-platform comparison for {current_product.get('title', 'this product')}:"]
    if current_product.get("rating_text") or current_product.get("reviewCount"):
        summary = current_product.get("rating_text") or current_product.get("rating") or "No rating found"
        if current_product.get("reviewCount"):
            summary += f" with {current_product.get('reviewCount')}"
        lines.append(f"Current page review snapshot: {summary}")

    if comparison_products:
        for item in comparison_products:
            summary = f"- {item.get('platform', 'Platform')}: {item.get('price') or 'Price not found'}"
            if item.get("rating_text"):
                summary += f", rating {item.get('rating_text')}"
            elif item.get("rating"):
                summary += f", rating {item.get('rating')}/5"
            if item.get("reviewCount"):
                summary += f", reviews {item.get('reviewCount')}"
            if item.get("url"):
                summary += f", link: {item.get('url')}"
            lines.append(summary)
    else:
        lines.append("I could not find matching listings on the requested platforms yet.")

    lines.append("I kept this comparison in the same session, so you can continue asking about this product without changing the page.")

    return {
        "answer": "\n".join(lines),
        "product": current_product,
        "comparison": {
            "products": comparison_products,
            "query": search_query,
        },
    }


async def current_page_asking(user_query: str, current_page_url: str):
    try:
        print(f"\n{'='*80}")
        print(f"[ASKING] Processing query: {user_query}")
        print(f"[ASKING] Current URL: {current_page_url}")
        print(f"{'='*80}\n")

        non_scrapable_schemes = ['chrome://', 'chrome-extension://', 'about:', 'file://', 'data:', 'javascript:', 'edge://', 'brave://']
        is_non_scrapable = any(current_page_url.lower().startswith(scheme) for scheme in non_scrapable_schemes)

        if is_non_scrapable:
            return {
                "answer": (
                    "I can't analyze browser-internal pages like new tabs or extension pages. "
                    "Please navigate to an e-commerce product page (Amazon, Flipkart, etc.) "
                    "and I'll be happy to help you analyze the product!"
                )
            }

        print("[ASKING] Attempting Method 1: Vector embeddings...")
        context = await current_page_context(current_page_url, user_query)

        if isinstance(context, list) and len(context) > 0:
            context_strings = [item[0] if isinstance(item, tuple) else item for item in context]
            context_text = "\n".join(context_strings)
            print(f"[ASKING] Method 1 SUCCESS: Using {len(context_strings)} embedding chunks")
        elif isinstance(context, list) and len(context) == 0:
            print("[ASKING] Method 1 FAILED: No embeddings found")
            print("[ASKING] Attempting Method 2: Direct scraping fallback...")

            try:
                from helpers.web_scrapper import web_scrapper

                direct_chunks = await web_scrapper(current_page_url, full_page=True)

                if direct_chunks and len(direct_chunks) > 0:
                    context_text = "\n\n".join(direct_chunks[:5])
                    print(f"[ASKING] Method 2 SUCCESS: Using {min(5, len(direct_chunks))} direct chunks ({len(context_text)} chars)")
                else:
                    print("[ASKING] Method 2 FAILED: Could not scrape page")
                    context_text = "ERROR: Unable to extract any information from this page. The page may be blocking automated access."
            except Exception as scrape_error:
                print(f"[ASKING] Method 2 CRITICAL ERROR: {scrape_error}")
                import traceback

                traceback.print_exc()
                context_text = f"ERROR: Failed to access page content due to: {str(scrape_error)}"
        else:
            context_text = str(context) if context else "No context available."
            print(f"[ASKING] Unexpected context type: {type(context)}")

        print(f"[ASKING] Building prompt with context length: {len(context_text)} characters")
        print(f"[ASKING] Context preview: {context_text[:300]}...")

        structured_context = await _get_structured_product_context(current_page_url, context_text)
        product_payload = _product_payload_from_context(current_page_url, structured_context)

        if _is_compare_query(user_query):
            print("[ASKING] Compare intent detected for current product, using cross-platform comparison flow")
            return await compare_current_product(user_query, current_page_url, structured_context)

        prompt = currentpage_asking_prompt(context_text)
        messages = [SystemMessage(content=prompt), HumanMessage(content=user_query)]

        print("[ASKING] Sending to LLM provider...")
        try:
            response = await invoke_llm_with_fallback(messages, "general")
        except Exception as llm_error:
            normalized = normalize_llm_exception(llm_error)
            if isinstance(normalized, (LLMConfigurationError, LLMServiceUnavailableError)):
                print(f"[ASKING] LLM unavailable, using deterministic fallback: {normalized}")
                return {
                    "answer": _fallback_current_page_answer(user_query, current_page_url, structured_context),
                    "product": product_payload,
                }
            raise normalized

        answer = response.content if response and response.content else "I couldn't generate a response. Please try again."
        print(f"[ASKING] AI Response received: {len(answer)} characters")
        print(f"[ASKING] Response preview: {answer[:200]}...")
        print(f"{'='*80}\n")

        return {
            "answer": answer,
            "product": product_payload,
        }

    except Exception as e:
        normalized = normalize_llm_exception(e)
        if normalized is not e:
            raise normalized
        print(f"[ERROR] Error in current_page_asking: {e}")
        import traceback

        traceback.print_exc()
        return {"answer": "I encountered an error while processing your question. Please try again."}


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
                return {
                    "answer": (
                        "I could not reach an LLM provider. "
                        f"I did complete product retrieval for domain '{domain}', but I cannot generate a recommendation summary right now."
                    )
                }
            raise normalized

        answer = response.content if response and response.content else "I couldn't generate a response. Please try again."
        print(f"[LOG] Generated answer: {answer[:100]}...")
        return {"answer": answer}

    except Exception as e:
        normalized = normalize_llm_exception(e)
        if normalized is not e:
            raise normalized
        print(f"[ERROR] Error in product_asking: {e}")
        import traceback

        traceback.print_exc()
        return {"answer": "I encountered an error while processing your product question. Please try again."}


async def chat_history_asking(user_query: str, chat_history: str):
    try:
        prompt = chat_history_response_prompt(user_query, chat_history)
        messages = [SystemMessage(content=prompt), HumanMessage(content=user_query)]
        try:
            response = await invoke_llm_with_fallback(messages, "general")
        except Exception as llm_error:
            normalized = normalize_llm_exception(llm_error)
            if isinstance(normalized, (LLMConfigurationError, LLMServiceUnavailableError)):
                return {
                    "answer": "I could not reach an LLM provider, so I cannot summarize prior chat history right now."
                }
            raise normalized
        answer = response.content if response and response.content else "I couldn't generate a response. Please try again."
        print(f"[LOG] Generated answer: {answer[:100]}...")
        return {"answer": answer}
    except Exception as e:
        normalized = normalize_llm_exception(e)
        if normalized is not e:
            raise normalized
        print(f"[ERROR] Error in chat_history_asking: {e}")
        import traceback

        traceback.print_exc()
        return {"answer": "I encountered an error while processing your chat history question. Please try again."}


async def asking(user_query: str, domain: str, current_page_url: str, scope: str, session_id: str, chat_history: str):
    print(f"[LOG] asking() called with scope: {scope}")

    if scope == "current_page":
        return await current_page_asking(user_query, current_page_url)
    if scope == "product":
        print(f"[LOG] Product scope detected, using product_asking")
        return await product_asking(user_query, domain)
    if scope == "chat_history":
        return await chat_history_asking(user_query, chat_history)

    print(f"[WARNING] Unknown scope: {scope}, using current_page_asking as fallback")
    return await current_page_asking(user_query, current_page_url)
