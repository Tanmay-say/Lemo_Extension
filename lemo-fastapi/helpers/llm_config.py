"""LLM provider configuration.

Gemini is now served by `helpers.gemini_client` (official `google-genai` SDK).
LangChain is kept only for the Emergent / OpenAI-compatible fallback provider,
so legacy code paths in `cases/asking.py` continue to work.

Public API preserved so that `controllers.query_handler` and the legacy asking
flow keep their error-handling contracts:
    - LLMConfigurationError / LLMServiceUnavailableError
    - normalize_llm_exception / user_facing_llm_message
    - get_llm_for_task / invoke_llm_with_fallback
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Iterable, Optional
from urllib.parse import urlparse

import httpx

from core.config import (
    chat_model_name,
    emergent_base_url,
    get_llm_keys,
    llm_max_retries,
    llm_provider_preference,
    llm_request_timeout,
)

try:
    from openai import APIConnectionError as OpenAIAPIConnectionError
except Exception:  # pragma: no cover
    OpenAIAPIConnectionError = tuple()  # type: ignore[assignment]


logger = logging.getLogger(__name__)


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


# ---------------------------------------------------------------------------
# Gemini adapter — presents a LangChain-ish interface over gemini_client.
# ---------------------------------------------------------------------------


class _GeminiResponse:
    """Minimal ducktype for LangChain `AIMessage`. Only `.content` is read."""

    __slots__ = ("content",)

    def __init__(self, content: str):
        self.content = content


def _split_langchain_messages(messages: Iterable[Any]) -> tuple[str, str]:
    """Flatten LangChain message list into (system, user) strings.

    System messages are concatenated with newlines; human messages likewise.
    Other message types are appended to the user string with a role prefix.
    """
    system_parts: list[str] = []
    user_parts: list[str] = []

    for msg in messages:
        msg_type = getattr(msg, "type", None)
        content = getattr(msg, "content", None)
        if content is None and isinstance(msg, dict):
            msg_type = msg.get("type") or msg.get("role")
            content = msg.get("content")
        if not content:
            continue

        text = content if isinstance(content, str) else str(content)
        if msg_type in ("system", "developer"):
            system_parts.append(text)
        elif msg_type in ("human", "user"):
            user_parts.append(text)
        elif msg_type in ("ai", "assistant"):
            user_parts.append(f"[assistant previously said] {text}")
        else:
            user_parts.append(text)

    return "\n\n".join(system_parts), "\n\n".join(user_parts) or ""


class _GeminiChatAdapter:
    """Lightweight LangChain-compatible wrapper around `gemini_client`.

    Supports:
        * `await adapter.ainvoke(messages)` → `_GeminiResponse`
        * `adapter.with_structured_output(Schema)` → adapter with schema bound
    """

    def __init__(self, model: str, temperature: float, schema: type | None = None):
        self._model = model
        self._temperature = temperature
        self._schema = schema

    def with_structured_output(self, schema: type) -> "_GeminiChatAdapter":
        return _GeminiChatAdapter(self._model, self._temperature, schema=schema)

    async def ainvoke(self, messages: Iterable[Any]) -> Any:
        from helpers import gemini_client

        system, user = _split_langchain_messages(messages)
        if not user.strip():
            user = "(no user content)"

        if self._schema is not None:
            return await gemini_client.generate(
                user=user,
                model=self._model,
                system=system or None,
                temperature=self._temperature,
                schema=self._schema,
            )

        text = await gemini_client.generate(
            user=user,
            model=self._model,
            system=system or None,
            temperature=self._temperature,
        )
        return _GeminiResponse(text if isinstance(text, str) else str(text))


def _build_gemini_client(model: str, temperature: float) -> _GeminiChatAdapter:
    logger.info("[LLM] Using Google Gemini model '%s' via google-genai SDK", model)
    return _GeminiChatAdapter(model=model, temperature=temperature)


def _build_emergent_client(model: str, temperature: float):
    from langchain_openai import ChatOpenAI
    llm_keys = get_llm_keys()

    base_url = _validate_base_url(emergent_base_url())
    logger.info("[LLM] Using Emergent proxy at '%s' with model '%s'", base_url, model)
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
    """Return a ducktype LangChain chat client for legacy callers.

    New code should prefer `helpers.gemini_client` directly.
    """
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
            logger.warning("[LLM] Failed to initialize provider '%s': %s", selected_provider, exc)

    if last_error is not None:
        raise LLMServiceUnavailableError("Unable to initialize any configured LLM provider.") from last_error

    raise LLMConfigurationError("Unable to select an LLM provider.")


def is_llm_connection_error(exc: Exception) -> bool:
    return isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout)) or (
        OpenAIAPIConnectionError and isinstance(exc, OpenAIAPIConnectionError)
    )


def is_llm_auth_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        "permission denied" in message
        or "consumer_suspended" in message
        or "api key" in message
        or "unauthenticated" in message
    )


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
    """Try each available provider in order, returning the first success.

    Gemini is served by `gemini_client` (no LangChain dependency).
    Emergent still uses `langchain-openai`.
    """
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
