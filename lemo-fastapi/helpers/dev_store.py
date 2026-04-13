import asyncio
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.config import database_configured

_lock = asyncio.Lock()
_store_path = Path(os.getenv("LEMO_DEV_STORE_PATH", "/tmp/lemo-fastapi-dev-store.json"))


def use_dev_store() -> bool:
    return not database_configured()


def _default_store() -> Dict[str, Any]:
    return {"users": {}, "sessions": {}, "messages": {}}


def _read_store() -> Dict[str, Any]:
    if not _store_path.exists():
        return _default_store()
    try:
        return json.loads(_store_path.read_text(encoding="utf-8"))
    except Exception:
        return _default_store()


def _write_store(data: Dict[str, Any]) -> None:
    _store_path.parent.mkdir(parents=True, exist_ok=True)
    _store_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


async def get_user(wallet_address: str) -> Optional[Dict[str, Any]]:
    async with _lock:
        store = _read_store()
        return store["users"].get(wallet_address.strip().lower())


async def create_or_update_user(wallet_address: str, email: str = "", first_name: str = "", last_name: str = "", other_details: Any = None) -> Dict[str, Any]:
    async with _lock:
        store = _read_store()
        normalized = wallet_address.strip().lower()
        now = datetime.utcnow().isoformat()
        user = store["users"].get(normalized) or {
            "id": normalized,
            "wallet_address": normalized,
            "created_at": now,
        }
        user.update(
            {
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "other_details": other_details,
                "is_active": True,
                "updated_at": now,
            }
        )
        store["users"][normalized] = user
        _write_store(store)
        return user


async def create_session(user_id: str, current_url: str, current_domain: str) -> Dict[str, Any]:
    async with _lock:
        store = _read_store()
        session_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        session = {
            "id": session_id,
            "user_id": user_id,
            "current_url": current_url,
            "current_domain": current_domain,
            "created_at": now,
            "updated_at": now,
        }
        store["sessions"][session_id] = session
        store["messages"][session_id] = []
        _write_store(store)
        return session


async def list_sessions(user_id: str) -> List[Dict[str, Any]]:
    async with _lock:
        store = _read_store()
        return [session for session in store["sessions"].values() if session.get("user_id") == user_id]


async def get_session(session_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    async with _lock:
        store = _read_store()
        session = store["sessions"].get(session_id)
        if not session:
            return None
        if user_id and session.get("user_id") != user_id:
            return None
        return session


async def add_message(session_id: str, user_id: str, message: str, message_type: str, detected_intent: Optional[str]) -> Dict[str, Any]:
    async with _lock:
        store = _read_store()
        session = store["sessions"].get(session_id)
        if not session or session.get("user_id") != user_id:
            raise ValueError("Session not found or unauthorized")

        record = {
            "id": str(uuid.uuid4()),
            "session_id": session_id,
            "user_id": user_id,
            "message": message,
            "message_type": message_type,
            "detected_intent": detected_intent,
            "created_at": datetime.utcnow().isoformat(),
        }
        store["messages"].setdefault(session_id, []).append(record)
        session["updated_at"] = datetime.utcnow().isoformat()
        _write_store(store)
        return record


async def get_session_with_messages(session_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    async with _lock:
        store = _read_store()
        session = store["sessions"].get(session_id)
        if not session:
            return None
        if user_id and session.get("user_id") != user_id:
            return None
        data = dict(session)
        data["chat_messages"] = list(store["messages"].get(session_id, []))
        return data
