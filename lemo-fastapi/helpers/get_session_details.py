from core.database import prisma, get_prisma
from helpers.dev_store import get_session_with_messages, use_dev_store

async def get_session_details(session_id: str, user_id: str):
    try:
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
        
        return session if isinstance(session, dict) else session.model_dump(mode='json')
        
    except ValueError as e:
        print(f"[ERROR] {e}")
        raise
    except Exception as e:
        print(f"[ERROR] Failed to get session details: {e}")
        raise
