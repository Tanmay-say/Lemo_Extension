import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import llm_keys
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from prompts.intent_detection import intent_detection_prompt
from pydantic import BaseModel, Field
from typing import Literal


class IntentOutput(BaseModel):
    """Structured output for intent detection."""
    intent: Literal["ask", "todo", "unknown"] = Field(description="The intent type")
    scope: Literal["current_page", "product", "cart", "order", "wishlist", "account", "chat_history", "unknown"] = Field(description="The scope of the intent")
    message_forward: str = Field(description="String that will be passed to the next AI agent")

async def intent_detection(user_query: str):
    # Get user input
    user_input = user_query

    # Initialize the Gemini Model
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.7,
        max_tokens=None,
        timeout=None,
        max_retries=2,
        api_key=llm_keys.gemini
    )

    # Apply structured output to the model
    structured_llm = llm.with_structured_output(IntentOutput)
    messages = []

    # Add system prompt and user input
    messages.append(SystemMessage(content=intent_detection_prompt))
    messages.append(HumanMessage(content=user_input))

    # Invoke the model and get structured output
    response = await structured_llm.ainvoke(messages)

    return response
