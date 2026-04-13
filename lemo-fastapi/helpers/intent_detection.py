import logging
import os
import sys
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from helpers.llm_config import normalize_llm_exception, get_llm_for_task
from prompts.intent_detection import intent_detection_prompt

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)


class IntentOutput(BaseModel):
    """Structured output for intent detection."""

    intent: Literal["ask", "todo", "unknown"] = Field(description="The intent type")
    scope: Literal[
        "current_page",
        "product",
        "cart",
        "order",
        "wishlist",
        "account",
        "chat_history",
        "unknown",
    ] = Field(description="The scope of the intent")
    message_forward: str = Field(description="String that will be passed to the next AI agent")


def _keyword_scope(user_query: str) -> str:
    query = user_query.lower()

    if any(token in query for token in ("previous", "earlier", "before", "last message", "chat history", "conversation")):
        return "chat_history"
    if any(token in query for token in ("cart", "basket", "checkout")):
        return "cart"
    if any(token in query for token in ("wishlist", "wish list", "saved item", "favorites", "favourites")):
        return "wishlist"
    if any(token in query for token in ("order", "delivery", "refund", "return", "shipping", "shipment", "track")):
        return "order"
    if any(token in query for token in ("account", "login", "sign in", "address book", "profile", "password")):
        return "account"
    if any(token in query for token in ("recommend", "suggest", "similar", "alternative", "best ", "compare")):
        return "product"
    if any(token in query for token in ("this page", "this product", "current page", "shown here", "on this page")):
        return "current_page"
    return "current_page"


def _keyword_intent(user_query: str) -> str:
    query = user_query.lower().strip()
    todo_prefixes = (
        "add ",
        "buy ",
        "order ",
        "remove ",
        "cancel ",
        "track ",
        "open ",
        "go to ",
        "show ",
        "apply ",
        "update ",
    )
    if query.startswith(todo_prefixes):
        return "todo"
    if "?" in query or any(query.startswith(word) for word in ("what", "which", "why", "how", "is", "are", "can", "should")):
        return "ask"
    return "ask"


def fallback_intent_detection(user_query: str) -> IntentOutput:
    return IntentOutput(
        intent=_keyword_intent(user_query),
        scope=_keyword_scope(user_query),
        message_forward=user_query.strip(),
    )


async def intent_detection(user_query: str) -> IntentOutput:
    llm = get_llm_for_task("analysis")
    structured_llm = llm.with_structured_output(IntentOutput)
    messages = [
        SystemMessage(content=intent_detection_prompt),
        HumanMessage(content=user_query),
    ]

    try:
        response = await structured_llm.ainvoke(messages)
        return response
    except Exception as exc:
        normalized = normalize_llm_exception(exc)
        logger.warning("Intent detection failed, using heuristic fallback: %s", normalized)
        return fallback_intent_detection(user_query)
