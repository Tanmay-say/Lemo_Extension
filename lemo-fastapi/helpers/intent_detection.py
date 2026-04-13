import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.messages import HumanMessage, SystemMessage
from prompts.intent_detection import intent_detection_prompt
from pydantic import BaseModel, Field
from typing import Literal
from helpers.llm_config import get_llm_for_task


class IntentOutput(BaseModel):
    """Structured output for intent detection."""
    intent: Literal["ask", "todo", "unknown"] = Field(description="The intent type")
    scope: Literal["current_page", "product", "cart", "order", "wishlist", "account", "chat_history", "unknown"] = Field(description="The scope of the intent")
    message_forward: str = Field(description="String that will be passed to the next AI agent")

async def intent_detection(user_query: str):
    llm = get_llm_for_task("analysis")
    structured_llm = llm.with_structured_output(IntentOutput)
    messages = [
        SystemMessage(content=intent_detection_prompt),
        HumanMessage(content=user_query),
    ]
    response = await structured_llm.ainvoke(messages)
    return response
