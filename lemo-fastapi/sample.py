import asyncio
import sys

from langchain_core.messages import HumanMessage, SystemMessage

from core.config import chat_model_name, get_llm_keys, llm_provider_preference
from helpers.llm_config import get_llm_for_task, normalize_llm_exception
async def main() -> int:
    dry_run = "--dry-run" in sys.argv[1:]
    args = [arg for arg in sys.argv[1:] if arg != "--dry-run"]
    prompt = " ".join(args).strip() or "Reply with one short sentence confirming the Gemini connection is working."
    keys = get_llm_keys()

    print(f"LLM_PROVIDER={llm_provider_preference()}")
    print(f"GEMINI_MODEL={chat_model_name('gemini')}")
    print(f"EMERGENT_MODEL={chat_model_name('emergent')}")
    print(f"GEMINI_CONFIGURED={str(bool(keys.gemini)).lower()}")
    print(f"EMERGENT_CONFIGURED={str(bool(keys.emergent)).lower()}")
    print(f"PROMPT={prompt}")
    print(f"DRY_RUN={str(dry_run).lower()}")

    if dry_run:
        return 0

    try:
        llm = get_llm_for_task("general")
        response = await llm.ainvoke(
            [
                SystemMessage(content="You are a concise test assistant."),
                HumanMessage(content=prompt),
            ]
        )
    except Exception as exc:
        normalized = normalize_llm_exception(exc)
        print(f"ERROR={type(normalized).__name__}: {normalized}")
        return 1

    content = response.content if response and response.content else ""
    print("RESPONSE_START")
    print(content)
    print("RESPONSE_END")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
