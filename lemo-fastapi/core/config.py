from dataclasses import dataclass, field
import os
from pathlib import Path

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
    """Return True only if DATABASE_URL is set AND the Prisma engine is available.

    Set USE_DEV_STORE=true in .env to force the JSON file fallback regardless.
    """
    # Explicit override: respect USE_DEV_STORE env var
    if _clean_env_value("USE_DEV_STORE", "").lower() in ("1", "true", "yes"):
        return False
    if is_placeholder(_clean_env_value("DATABASE_URL")):
        return False
    # Guard: check that the Prisma query engine exists in any of the known cache patterns
    try:
        import glob
        cache_patterns = [
            # binary engine (openssl 1.x / 3.0.x)
            str(Path.home() / ".cache" / "prisma-python" / "binaries" / "*" / "*" / "prisma-query-engine-*"),
            str(Path(__file__).parent.parent / "prisma-query-engine-*"),
            # library engine (.so.node) — fetched on openssl 3.x systems
            str(Path.home() / ".cache" / "prisma-python" / "binaries" / "*" / "*" / "node_modules" / "@prisma" / "engines" / "libquery_engine-*.so.node"),
        ]
        if not any(glob.glob(p) for p in cache_patterns):
            print(
                "[CONFIG] Prisma engine not found in cache. "
                "Run `prisma py fetch` then restart. Falling back to dev-store."
            )
            return False
    except Exception as _err:
        print(f"[CONFIG] Could not check Prisma engine: {_err}. Falling back to dev-store.")
        return False
    return True





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
