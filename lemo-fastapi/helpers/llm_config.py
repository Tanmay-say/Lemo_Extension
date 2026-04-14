import logging
from typing import Optional
from urllib.parse import urlparse

import httpx

from core.config import chat_model_name, emergent_base_url, get_llm_keys, llm_max_retries, llm_provider_preference, llm_request_timeout

try:
    from openai import APIConnectionError as OpenAIAPIConnectionError
except Exception:  # pragma: no cover - keeps imports resilient during partial installs
    OpenAIAPIConnectionError = tuple()  # type: ignore[assignment]


logger = logging.getLogger(__name__)

try:
    from google.api_core.exceptions import PermissionDenied as GooglePermissionDenied
except Exception:  # pragma: no cover - keeps imports resilient during partial installs
    GooglePermissionDenied = tuple()  # type: ignore[assignment]


class LLMConfigurationError(ValueError):
    """Raised when LLM credentials or configuration are invalid."""


class LLMServiceUnavailableError(RuntimeError):
    """Raised when the configured LLM provider cannot be reached."""


def is_valid_key(key: Optional[str]) -> bool:
    return bool(key and len(key.strip()) >= 10 and "PLACEHOLDER" not in key.upper())


def _temperatures() -> dict[str, float]:
    return {
        "general": 0.7,
        "code": 0.2,
        "creative": 0.9,
        "analysis": 0.3,
    }


def _available_providers() -> list[str]:
    llm_keys = get_llm_keys()
    providers: list[str] = []
    if is_valid_key(llm_keys.gemini):
        providers.append("gemini")
    if is_valid_key(llm_keys.emergent):
        providers.append("emergent")
    return providers


def _provider_order() -> list[str]:
    preferred = llm_provider_preference()
    available = _available_providers()

    if preferred == "auto":
        ordered = [provider for provider in ("gemini", "emergent") if provider in available]
    else:
        ordered = [preferred] if preferred in available else []
        if not ordered:
            fallback = [provider for provider in ("gemini", "emergent") if provider in available]
            if fallback:
                logger.warning(
                    "LLM_PROVIDER='%s' is not fully configured. Falling back to available provider(s): %s",
                    preferred,
                    ", ".join(fallback),
                )
                ordered = fallback

    if ordered:
        return ordered

    raise LLMConfigurationError(
        "No LLM API key configured. Set GEMINI_API_KEY (recommended) or EMERGENT_LLM_KEY in your .env file."
    )


def _validate_base_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise LLMConfigurationError(
            f"EMERGENT_BASE_URL is invalid: '{base_url}'. Expected a full URL such as https://api.emergent.ai/v1."
        )
    return base_url.rstrip("/")


def _build_gemini_client(model: str, temperature: float):
    from langchain_google_genai import ChatGoogleGenerativeAI
    llm_keys = get_llm_keys()

    print(f"[LLM] Using Google Gemini model '{model}'")
    return ChatGoogleGenerativeAI(
        model=model,
        google_api_key=llm_keys.gemini,
        temperature=temperature,
        max_output_tokens=2048,
        timeout=llm_request_timeout(),
    )


def _build_emergent_client(model: str, temperature: float):
    from langchain_openai import ChatOpenAI
    llm_keys = get_llm_keys()

    base_url = _validate_base_url(emergent_base_url())
    print(f"[LLM] Using Emergent proxy at '{base_url}' with model '{model}'")
    return ChatOpenAI(
        model=model,
        api_key=llm_keys.emergent,
        base_url=base_url,
        temperature=temperature,
        max_tokens=2048,
        timeout=llm_request_timeout(),
        max_retries=llm_max_retries(),
    )


def get_llm_for_task(task_type: str = "general", provider: str | None = None):
    temperature = _temperatures().get(task_type, 0.7)
    last_error: Exception | None = None

    provider_order = [provider] if provider else _provider_order()

    for selected_provider in provider_order:
        try:
            model = chat_model_name(selected_provider)
            if selected_provider == "gemini":
                return _build_gemini_client(model, temperature)
            if selected_provider == "emergent":
                return _build_emergent_client(model, temperature)
        except LLMConfigurationError:
            raise
        except Exception as exc:
            last_error = exc
            print(f"[LLM] Failed to initialize provider '{selected_provider}': {exc}")

    if last_error is not None:
        raise LLMServiceUnavailableError("Unable to initialize any configured LLM provider.") from last_error

    raise LLMConfigurationError("Unable to select an LLM provider.")


def is_llm_connection_error(exc: Exception) -> bool:
    return isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout)) or (
        OpenAIAPIConnectionError and isinstance(exc, OpenAIAPIConnectionError)
    )


def is_llm_auth_error(exc: Exception) -> bool:
    if GooglePermissionDenied and isinstance(exc, GooglePermissionDenied):
        return True
    message = str(exc).lower()
    return "permission denied" in message or "consumer_suspended" in message or "api key" in message


def normalize_llm_exception(exc: Exception) -> Exception:
    if isinstance(exc, (LLMConfigurationError, LLMServiceUnavailableError)):
        return exc
    if is_llm_auth_error(exc):
        return LLMConfigurationError(
            "The configured Gemini API key was rejected by Google. "
            "Update GEMINI_API_KEY in lemo-fastapi/.env or the server environment, then restart the FastAPI server."
        )
    if is_llm_connection_error(exc):
        return LLMServiceUnavailableError(
            "The configured LLM provider could not be reached. "
            "If you are using Emergent, verify DNS/network access to the API host or switch to a valid GEMINI_API_KEY."
        )
    return exc


def user_facing_llm_message(exc: Exception) -> str:
    normalized = normalize_llm_exception(exc)
    if isinstance(normalized, LLMConfigurationError):
        return str(normalized)
    if isinstance(normalized, LLMServiceUnavailableError):
        return str(normalized)
    return "An unexpected LLM error occurred while processing the request."


async def invoke_llm_with_fallback(messages, task_type: str = "general"):
    last_error: Exception | None = None

    for provider in _provider_order():
        try:
            llm = get_llm_for_task(task_type, provider=provider)
            return await llm.ainvoke(messages)
        except Exception as exc:
            normalized = normalize_llm_exception(exc)
            last_error = normalized
            logger.warning("LLM provider '%s' failed during invocation: %s", provider, normalized)
            continue

    if last_error is not None:
        raise last_error
    raise LLMConfigurationError("Unable to select an LLM provider.")
