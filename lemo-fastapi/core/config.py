from dataclasses import dataclass, field
import os
from pathlib import Path

from dotenv import load_dotenv

ENV_PATH = Path(__file__).parent.parent / ".env"


def _reload_project_env(override: bool = False) -> None:
    load_dotenv(dotenv_path=ENV_PATH, override=override)


_reload_project_env()


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


def get_llm_keys() -> LLMKeys:
    # Re-read the project .env so key updates are reflected without requiring a
    # fresh Python process.
    _reload_project_env(override=True)
    return LLMKeys()


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


def llm_provider_preference() -> str:
    _reload_project_env(override=True)
    value = _clean_env_value("LLM_PROVIDER", "auto").lower()
    return value if value in {"auto", "gemini", "emergent"} else "auto"


def llm_request_timeout() -> float:
    _reload_project_env(override=True)
    value = _clean_env_value("LLM_TIMEOUT_SECONDS", "30")
    try:
        return max(5.0, float(value))
    except ValueError:
        return 30.0


def llm_max_retries() -> int:
    _reload_project_env(override=True)
    value = _clean_env_value("LLM_MAX_RETRIES", "2")
    try:
        return max(0, int(value))
    except ValueError:
        return 2


def chat_model_name(provider: str | None = None) -> str:
    _reload_project_env(override=True)

    keys_by_provider = {
        "gemini": ("GEMINI_MODEL", "LLM_MODEL"),
        "emergent": ("EMERGENT_MODEL", "LLM_MODEL"),
    }
    ordered_keys = keys_by_provider.get(provider or "", ("EMERGENT_MODEL", "GEMINI_MODEL", "LLM_MODEL"))

    for key in ordered_keys:
        value = _clean_env_value(key)
        if value and not is_placeholder(value):
            return value

    if provider == "emergent":
        return "gpt-4.1-mini"
    return "gemini-2.5-flash-lite"
