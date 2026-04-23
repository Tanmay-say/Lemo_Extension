from __future__ import annotations

from core.database import prisma, get_prisma
from helpers.dev_store import get_session_with_messages, use_dev_store
from helpers.runtime_cache import delete, get_json, set_json

SESSION_CACHE_TTL_SECONDS = 2 * 60


def _session_cache_key(session_id: str, user_id: str) -> str:
    return f"session:details:{session_id}:{user_id}"


async def invalidate_session_details_cache(session_id: str, user_id: str) -> None:
    await delete(_session_cache_key(session_id, user_id))


async def get_session_details(session_id: str, user_id: str):
    try:
        cached = await get_json(_session_cache_key(session_id, user_id))
        if isinstance(cached, dict):
            return cached

        if use_dev_store():
            session = await get_session_with_messages(session_id, user_id)
        else:
            await get_prisma()
            session = await prisma.chat_sessions.find_first(
                where={
                    "id": session_id,
                    "user_id": user_id
                },
                include={
                    "users": False,
                    "chat_messages": {
                        "include": {
                            "users": False,
                        },
                        "order_by": {
                            "created_at": "asc"
                        }
                    }
                }
            )

        if not session:
            raise ValueError(f"Session not found for session_id: {session_id}")

        payload = session if isinstance(session, dict) else session.model_dump(mode="json")
        await set_json(_session_cache_key(session_id, user_id), payload, SESSION_CACHE_TTL_SECONDS)
        return payload

    except ValueError as e:
        print(f"[ERROR] {e}")
        raise
    except Exception as e:
        print(f"[ERROR] Failed to get session details: {e}")
        raise
