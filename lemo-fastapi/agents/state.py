"""Shared state for the LEMO LangGraph pipeline.

LangGraph hands the same mutable `LemoState` TypedDict around to every node.
Nodes return a partial dict; LangGraph merges it into the state automatically.
"""

from __future__ import annotations

from typing import Any, List, Literal, Optional, TypedDict


Intent = Literal["ask", "todo", "unknown"]

Scope = Literal[
    "current_page",
    "product",
    "cart",
    "order",
    "wishlist",
    "account",
    "chat_history",
    "unknown",
]

NextAction = Literal[
    "answer_from_history",      # Lemo can answer from chat_history alone
    "scrape_current_page",      # Need structured data from the active tab
    "discover_and_compare",     # Run cross-platform SERP + scrape
    "chat_history_summary",     # Summarise previous conversation
    "direct_answer",            # LLM-only answer, no scraping needed
]


class ChatTurn(TypedDict, total=False):
    message_type: str   # "user" | "assistant"
    message: str
    detected_intent: Optional[str]
    created_at: Optional[str]


class ScrapedProduct(TypedDict, total=False):
    platform: str
    title: str
    price: str
    rating: str
    rating_text: str
    reviewCount: str
    description: str
    features: str
    image: str
    url: str
    match_score: float   # rapidfuzz token_set_ratio vs. reference title


class LemoState(TypedDict, total=False):
    # --- inputs (populated by query_handler) ---
    user_query: str
    session_id: str
    user_id: str
    domain: str
    current_page_url: str
    chat_history: List[ChatTurn]
    cached_intent: Optional[dict]

    # --- produced by intent_tracker ---
    intent: Intent
    scope: Scope
    next_action: NextAction
    query_for_scraper: str
    intent_reasoning: str

    # --- produced by scraper_agent ---
    current_product: Optional[ScrapedProduct]
    scraped_data: List[ScrapedProduct]
    current_page_context: str   # raw text chunks for LLM grounding

    # --- produced by lemo_agent ---
    final_answer: str
    product: Optional[dict]
    comparison: Optional[dict]

    # --- diagnostics ---
    errors: List[str]
