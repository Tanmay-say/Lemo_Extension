"""Thin wrapper around the official `google-genai` SDK.

This module is the single point of contact for Gemini 3.1 Pro / Flash and the
`gemini-embedding-001` embedding model. The rest of the backend imports from
here so we can swap SDKs in one place.

Error handling intentionally maps every SDK exception to one of the two custom
exceptions already defined in `helpers.llm_config` so the existing 500 / 503
paths in `controllers/query_handler.py` keep working unchanged:

    LLMConfigurationError   -> auth, model-not-found, bad API key (HTTP 500)
    LLMServiceUnavailableError -> timeouts, network, rate limit (HTTP 503)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Iterable, Optional

from core.config import (
    gemini_embed_model,
    gemini_fast_model,
    chat_model_name,
    get_llm_keys,
    llm_request_timeout,
    llm_stream_timeout,
)

logger = logging.getLogger(__name__)


# Imported lazily so the module is still importable when the dependency is not
# yet installed (e.g. during `pip install` on fresh checkouts).
def _load_sdk():
    try:
        from google import genai  # type: ignore
        from google.genai import types as genai_types  # type: ignore
    except ImportError as exc:  # pragma: no cover - import-time guard
        raise ImportError(
            "The `google-genai` package is required. Install it with "
            "`pip install google-genai>=1.0.0`."
        ) from exc
    return genai, genai_types


_client: Any | None = None


def _get_client():
    """Return a lazily-constructed singleton `genai.Client` instance."""
    global _client
    if _client is not None:
        return _client

    from helpers.llm_config import LLMConfigurationError

    keys = get_llm_keys()
    if not keys.gemini:
        raise LLMConfigurationError(
            "GEMINI_API_KEY is not configured. Add it to lemo-fastapi/.env and restart."
        )

    genai, _ = _load_sdk()
    _client = genai.Client(api_key=keys.gemini)
    logger.info("[gemini_client] Initialized google-genai client")
    return _client


def reset_client() -> None:
    """Reset the cached client — used by tests or when the API key rotates."""
    global _client
    _client = None


# ---------------------------------------------------------------------------
# Error mapping
# ---------------------------------------------------------------------------

_AUTH_MARKERS = (
    "permission denied",
    "api key",
    "api_key",
    "unauthenticated",
    "consumer_suspended",
    "invalid_argument",
    "not found",
    "model not found",
    "not supported",
)

_TRANSIENT_MARKERS = (
    "deadline",
    "timeout",
    "unavailable",
    "connection",
    "rate limit",
    "resource_exhausted",
    "429",
    "503",
    "504",
)


def _wrap_exception(exc: Exception) -> Exception:
    from helpers.llm_config import (
        LLMConfigurationError,
        LLMServiceUnavailableError,
    )

    if isinstance(exc, (LLMConfigurationError, LLMServiceUnavailableError)):
        return exc

    message = str(exc).lower()

    if any(marker in message for marker in _AUTH_MARKERS):
        return LLMConfigurationError(
            "Gemini rejected the request: "
            f"{exc}. Check GEMINI_API_KEY and GEMINI_MODEL in lemo-fastapi/.env."
        )
    if any(marker in message for marker in _TRANSIENT_MARKERS):
        return LLMServiceUnavailableError(
            f"Gemini provider is temporarily unavailable: {exc}"
        )
    return exc


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def _build_config(
    system: Optional[str],
    temperature: float,
    max_output_tokens: int,
    schema: Optional[type] = None,
    thinking_budget: Optional[int] = None,
):
    """Build a `GenerateContentConfig` for the `google-genai` SDK.

    `thinking_budget` controls how many tokens Gemini 3.x "thinking" models
    reserve for internal reasoning before producing user-visible output. If
    left at `None`, we default to `0` for structured output (schema != None,
    e.g. intent detection) and let the model choose otherwise. Set to a
    positive int to cap the reasoning budget explicitly.
    """
    _, genai_types = _load_sdk()

    cfg_kwargs: dict[str, Any] = {
        "temperature": temperature,
        "max_output_tokens": max_output_tokens,
    }
    if system:
        cfg_kwargs["system_instruction"] = system
    if schema is not None:
        cfg_kwargs["response_mime_type"] = "application/json"
        cfg_kwargs["response_schema"] = schema
        if thinking_budget is None:
            thinking_budget = 0

    if thinking_budget is not None:
        try:
            cfg_kwargs["thinking_config"] = genai_types.ThinkingConfig(
                thinking_budget=thinking_budget,
            )
        except Exception as exc:  # pragma: no cover - SDK-version guard
            logger.debug("[gemini_client] ThinkingConfig unavailable: %s", exc)

    return genai_types.GenerateContentConfig(**cfg_kwargs)


async def generate(
    user: str,
    *,
    model: Optional[str] = None,
    system: Optional[str] = None,
    temperature: float = 0.7,
    max_output_tokens: int = 2048,
    schema: Optional[type] = None,
    thinking_budget: Optional[int] = None,
) -> Any:
    """Single-shot Gemini generation.

    Returns:
        - The parsed pydantic instance when `schema` is provided and parsing
          succeeds, otherwise the raw text string.
    """
    model_name = model or chat_model_name("gemini")
    config = _build_config(
        system, temperature, max_output_tokens, schema, thinking_budget
    )

    def _call() -> Any:
        client = _get_client()
        response = client.models.generate_content(
            model=model_name,
            contents=user,
            config=config,
        )

        if schema is not None:
            # The new SDK attaches the parsed pydantic object at `response.parsed`
            # when response_schema is used. Fall back to JSON->pydantic manually.
            parsed = getattr(response, "parsed", None)
            if parsed is not None:
                return parsed
            text = getattr(response, "text", None) or ""
            if text:
                try:
                    return schema.model_validate_json(text)
                except Exception as parse_err:  # pragma: no cover
                    logger.warning(
                        "[gemini_client] Failed to parse structured output: %s. Raw: %s",
                        parse_err,
                        text[:200],
                    )
            return None

        return getattr(response, "text", "") or ""

    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_call),
            timeout=llm_request_timeout(),
        )
    except asyncio.TimeoutError as exc:
        from helpers.llm_config import LLMServiceUnavailableError
        raise LLMServiceUnavailableError(
            f"Gemini request exceeded timeout of {llm_request_timeout()}s"
        ) from exc
    except Exception as exc:
        raise _wrap_exception(exc) from exc


async def stream(
    user: str,
    *,
    model: Optional[str] = None,
    system: Optional[str] = None,
    temperature: float = 0.7,
    max_output_tokens: int = 2048,
    thinking_budget: Optional[int] = None,
) -> str:
    """Stream Gemini generation and return the concatenated text.

    Streaming is useful for the Lemo agent's final answer — we still return the
    full string so the existing JSON-response contract is preserved, but this
    path gives us better latency for long responses and unblocks future token
    streaming to the Chrome extension.
    """
    model_name = model or chat_model_name("gemini")
    config = _build_config(
        system, temperature, max_output_tokens, schema=None,
        thinking_budget=thinking_budget,
    )

    def _call() -> str:
        client = _get_client()
        chunks: list[str] = []
        for chunk in client.models.generate_content_stream(
            model=model_name,
            contents=user,
            config=config,
        ):
            text = getattr(chunk, "text", None)
            if text:
                chunks.append(text)
        return "".join(chunks)

    stream_budget = llm_stream_timeout()
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_call),
            timeout=stream_budget,
        )
    except asyncio.TimeoutError as exc:
        from helpers.llm_config import LLMServiceUnavailableError
        raise LLMServiceUnavailableError(
            f"Gemini stream exceeded timeout of {stream_budget}s"
        ) from exc
    except Exception as exc:
        raise _wrap_exception(exc) from exc


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------

EMBED_DIM = 768  # pinned to 768 so Redis HNSW index stays compatible


async def embed(text: str, *, model: Optional[str] = None) -> list[float]:
    """Return a dense embedding for `text`. Always returns `EMBED_DIM` floats.

    `gemini-embedding-001` defaults to 3072 dims; we explicitly request 768
    via `output_dimensionality` so the existing Redis vector index keeps
    working without a schema migration.
    """
    if not text or not text.strip():
        raise ValueError("Input text is empty.")

    text = text.strip()[:8000]
    model_name = model or gemini_embed_model()

    def _call() -> list[float]:
        _, genai_types = _load_sdk()
        client = _get_client()
        try:
            embed_config = genai_types.EmbedContentConfig(
                output_dimensionality=EMBED_DIM,
            )
            response = client.models.embed_content(
                model=model_name,
                contents=text,
                config=embed_config,
            )
        except TypeError:
            # Older SDK builds that don't support EmbedContentConfig — fall
            # back to the default dimensionality and let the caller pad/truncate.
            response = client.models.embed_content(
                model=model_name,
                contents=text,
            )
        embeddings = getattr(response, "embeddings", None) or []
        if not embeddings:
            raise RuntimeError("Gemini embed_content returned no embeddings")
        values = getattr(embeddings[0], "values", None) or []
        if not values:
            raise RuntimeError("Gemini embed_content returned an empty vector")
        return list(values)

    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_call),
            timeout=llm_request_timeout(),
        )
    except asyncio.TimeoutError as exc:
        from helpers.llm_config import LLMServiceUnavailableError
        raise LLMServiceUnavailableError(
            f"Gemini embed exceeded timeout of {llm_request_timeout()}s"
        ) from exc
    except Exception as exc:
        raise _wrap_exception(exc) from exc


def embed_sync(text: str, *, model: Optional[str] = None) -> list[float]:
    """Synchronous wrapper around `embed` for code paths that are not async.

    Intentionally small — prefer `embed()` in async code.
    """
    return asyncio.run(embed(text, model=model))


# ---------------------------------------------------------------------------
# Convenience helpers used by the agent layer
# ---------------------------------------------------------------------------

def fast_model() -> str:
    return gemini_fast_model()


def pro_model() -> str:
    return chat_model_name("gemini")
