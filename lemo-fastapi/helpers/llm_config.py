from typing import Optional

from langchain_openai import ChatOpenAI

from core.config import chat_model_name, emergent_base_url, llm_keys


def is_valid_key(key: Optional[str]) -> bool:
    return bool(key and len(key.strip()) >= 10 and "PLACEHOLDER" not in key.upper())


def get_llm_for_task(task_type: str = "general"):
    temperature_map = {
        "general": 0.7,
        "code": 0.2,
        "creative": 0.9,
        "analysis": 0.3,
    }
    if not is_valid_key(llm_keys.emergent):
        raise ValueError("EMERGENT_LLM_KEY is not configured. Set a valid key in .env.")

    model = chat_model_name()
    temperature = temperature_map.get(task_type, 0.7)
    print(f"[LLM] Using Emergent with Gemini model '{model}'")
    return ChatOpenAI(
        model=model,
        api_key=llm_keys.emergent,
        base_url=emergent_base_url(),
        temperature=temperature,
        max_tokens=2048,
    )
