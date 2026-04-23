"""Text embedding helper.

Real embeddings are produced by `gemini-embedding-001` pinned to 768-dim. If the
API call fails (no key, network outage, quota, etc.) we fall back to a
deterministic 768-dim hash vector so `store_vector` / `search_similar` in
`redis_functions.py` never crash mid-request.

Product search has moved to rapidfuzz in the Scraper agent, so these
embeddings are primarily used for the current-page Q&A retrieval path.
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
from typing import List

logger = logging.getLogger(__name__)

# Pinned to 768 via `gemini_client.EMBED_DIM`. Legacy 384-dim vectors stored
# in Redis from previous versions will be rejected by `store_vector` on reload
# and naturally rewritten on the next scrape.
VECTOR_DIM = 768


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9_]+", text.lower())


def _hash_embedding(text_chunk: str) -> List[float]:
    """Deterministic hashing fallback — used only when Gemini embeddings fail.

    Preserves the old behaviour so retrieval still returns *something* sensible
    (token-overlap ranking) when we're offline or over quota.
    """
    vector = [0.0] * VECTOR_DIM
    tokens = _tokenize(text_chunk)
    if not tokens:
        return vector

    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % VECTOR_DIM
        sign = -1.0 if digest[4] % 2 else 1.0
        weight = 1.0 + (digest[5] / 255.0)
        vector[index] += sign * weight

    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def _gemini_embed_sync(text_chunk: str) -> List[float] | None:
    """Call the google-genai SDK synchronously. Returns None on any failure."""
    try:
        from helpers import gemini_client

        client = gemini_client._get_client()
        response = client.models.embed_content(
            model=_embed_model_name(),
            contents=text_chunk,
        )
        embeddings = getattr(response, "embeddings", None) or []
        if not embeddings:
            return None
        values = getattr(embeddings[0], "values", None) or []
        if not values:
            return None
        if len(values) != VECTOR_DIM:
            logger.warning(
                "[embedder] Gemini returned %d dims, expected %d — padding/truncating",
                len(values),
                VECTOR_DIM,
            )
            values = list(values)
            if len(values) < VECTOR_DIM:
                values = values + [0.0] * (VECTOR_DIM - len(values))
            else:
                values = values[:VECTOR_DIM]
        return list(values)
    except Exception as exc:
        logger.warning("[embedder] Gemini embedding failed, using hash fallback: %s", exc)
        return None


def _embed_model_name() -> str:
    from core.config import gemini_embed_model
    return gemini_embed_model()


def generate_embedding(text_chunk: str) -> List[float]:
    """Return a 768-dim embedding for `text_chunk`.

    Sync on purpose so the many existing callers don't need to be rewritten.
    Internally prefers `gemini-embedding-001` (forced to 768-dim) with a hashing fallback.
    """
    if not text_chunk or len(text_chunk.strip()) == 0:
        raise ValueError("Input text chunk is empty.")

    if len(text_chunk) > 4000:
        text_chunk = text_chunk[:4000]

    real = _gemini_embed_sync(text_chunk)
    if real is not None:
        return real

    return _hash_embedding(text_chunk)


async def generate_embedding_async(text_chunk: str) -> List[float]:
    """Async variant preferred by new code paths (e.g. agents).

    Uses the async path in `gemini_client.embed` and only falls back to the
    hashing vector when the API is unavailable.
    """
    if not text_chunk or len(text_chunk.strip()) == 0:
        raise ValueError("Input text chunk is empty.")

    if len(text_chunk) > 4000:
        text_chunk = text_chunk[:4000]

    try:
        from helpers import gemini_client

        values = await gemini_client.embed(text_chunk)
        if len(values) != VECTOR_DIM:
            if len(values) < VECTOR_DIM:
                values = values + [0.0] * (VECTOR_DIM - len(values))
            else:
                values = values[:VECTOR_DIM]
        return values
    except Exception as exc:
        logger.warning("[embedder] Async Gemini embedding failed, using hash fallback: %s", exc)
        return _hash_embedding(text_chunk)
