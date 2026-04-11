from dotenv import load_dotenv
import os
from dataclasses import dataclass, field

load_dotenv()


@dataclass
class LLMKeys:
    groq: str = field(default_factory=lambda: os.getenv("GROQ_API_KEY", ""))
    openai: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    gemini: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    # Add more keys here


REDIS_URL = os.getenv("REDIS_URL")
llm_keys = LLMKeys()