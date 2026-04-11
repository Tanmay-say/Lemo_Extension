from prisma import Prisma

prisma = Prisma()

async def get_session_details(session_id: str, user_id: str):
    try:
        # Connect to database if not connected
        if not prisma.is_connected():
            await prisma.connect()
        
        # Get session with messages
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
        
        return session.model_dump(mode='json')
        
    except ValueError as e:
        print(f"[ERROR] {e}")
        raise
    except Exception as e:
        print(f"[ERROR] Failed to get session details: {e}")
        raise