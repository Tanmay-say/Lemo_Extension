import hashlib
import math
import re

VECTOR_DIM = 384


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9_]+", text.lower())


def generate_embedding(text_chunk: str) -> list:
    if not text_chunk or len(text_chunk.strip()) == 0:
        raise ValueError("Input text chunk is empty.")
    if len(text_chunk) > 4000:
        text_chunk = text_chunk[:4000]
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
