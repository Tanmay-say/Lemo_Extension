from __future__ import annotations

import asyncio
import json
import time
from typing import Any

_LOCAL_CACHE: dict[str, tuple[float, str]] = {}
_LOCK = asyncio.Lock()
_REDIS_DISABLED_UNTIL = 0.0


def _redis_available() -> bool:
    return time.time() >= _REDIS_DISABLED_UNTIL


def _disable_redis_for(seconds: int = 60) -> None:
    global _REDIS_DISABLED_UNTIL
    _REDIS_DISABLED_UNTIL = max(_REDIS_DISABLED_UNTIL, time.time() + seconds)


async def _redis_get(key: str) -> str | None:
    if not _redis_available():
        return None
    try:
        from helpers.redis_functions import get_redis_connection

        r = await get_redis_connection()
        try:
            raw = await r.get(key)
        finally:
            await r.close()
        if raw is None:
            return None
        if isinstance(raw, bytes):
            return raw.decode("utf-8")
        return str(raw)
    except Exception:
        _disable_redis_for()
        return None


async def _redis_set(key: str, value: str, ttl_seconds: int) -> bool:
    if not _redis_available():
        return False
    try:
        from helpers.redis_functions import get_redis_connection

        r = await get_redis_connection()
        try:
            await r.setex(key, ttl_seconds, value)
        finally:
            await r.close()
        return True
    except Exception:
        _disable_redis_for()
        return False


async def _redis_delete(key: str) -> bool:
    if not _redis_available():
        return False
    try:
        from helpers.redis_functions import get_redis_connection

        r = await get_redis_connection()
        try:
            await r.delete(key)
        finally:
            await r.close()
        return True
    except Exception:
        _disable_redis_for()
        return False


async def get_json(key: str) -> Any | None:
    now = time.time()
    async with _LOCK:
        cached = _LOCAL_CACHE.get(key)
        if cached:
            expires_at, payload = cached
            if expires_at > now:
                return json.loads(payload)
            _LOCAL_CACHE.pop(key, None)

    raw = await _redis_get(key)
    if raw is None:
        return None
    try:
        value = json.loads(raw)
    except Exception:
        return None

    async with _LOCK:
        _LOCAL_CACHE[key] = (now + 30, raw)
    return value


async def set_json(key: str, value: Any, ttl_seconds: int) -> None:
    payload = json.dumps(value)
    await _redis_set(key, payload, ttl_seconds)
    async with _LOCK:
        _LOCAL_CACHE[key] = (time.time() + ttl_seconds, payload)


async def delete(key: str) -> None:
    await _redis_delete(key)
    async with _LOCK:
        _LOCAL_CACHE.pop(key, None)


async def clear_local_cache() -> None:
    global _REDIS_DISABLED_UNTIL
    async with _LOCK:
        _LOCAL_CACHE.clear()
    _REDIS_DISABLED_UNTIL = 0.0
