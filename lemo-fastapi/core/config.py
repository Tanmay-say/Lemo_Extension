from dataclasses import dataclass, field
import os

from dotenv import load_dotenv

load_dotenv()


def _clean_env_value(name: str, default: str = "") -> str:
    value = os.getenv(name, default)
    if value is None:
        return default
    return value.strip().strip('"').strip("'")


def is_placeholder(value: str) -> bool:
    cleaned = (value or "").strip()
    return not cleaned or "PLACEHOLDER" in cleaned.upper()


@dataclass
class LLMKeys:
    groq: str = field(default_factory=lambda: _clean_env_value("GROQ_API_KEY"))
    openai: str = field(default_factory=lambda: _clean_env_value("OPENAI_API_KEY"))
    gemini: str = field(default_factory=lambda: "" if is_placeholder(_clean_env_value("GEMINI_API_KEY")) else _clean_env_value("GEMINI_API_KEY"))
    emergent: str = field(default_factory=lambda: "" if is_placeholder(_clean_env_value("EMERGENT_LLM_KEY")) else _clean_env_value("EMERGENT_LLM_KEY"))


REDIS_URL = None if is_placeholder(_clean_env_value("REDIS_URL")) else _clean_env_value("REDIS_URL")
llm_keys = LLMKeys()


def database_configured() -> bool:
    return not is_placeholder(_clean_env_value("DATABASE_URL"))


def jwt_secret_key() -> str:
    configured = _clean_env_value("JWT_SECRET_KEY")
    if is_placeholder(configured):
        return "lemo-dev-insecure-jwt-secret-change-me"
    return configured


def emergent_base_url() -> str:
    return _clean_env_value("EMERGENT_BASE_URL", "https://api.emergent.ai/v1")


def chat_model_name() -> str:
    for key in ("EMERGENT_MODEL", "GEMINI_MODEL", "LLM_MODEL"):
        value = _clean_env_value(key)
        if value and not is_placeholder(value):
            return value
    return "gemini-2.5-flash"
