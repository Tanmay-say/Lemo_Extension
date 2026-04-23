from helpers.redis_functions import add_message_to_chat
from core.database import prisma, get_prisma
from helpers.dev_store import add_message as dev_add_message, use_dev_store
from helpers.get_session_details import invalidate_session_details_cache

async def add_chats(session_id: str, message: str, message_type: str, detected_intent: str, user_id: str):
    try:
        # Validate inputs
        if not session_id or not user_id:
            print("[ERROR] Session ID and User ID are required")
            return {"status": "error", "message": "Session ID and User ID are required"}
        
        if not message:
            print("[ERROR] Message is required")
            return {"status": "error", "message": "Message is required"}
        
        if message_type not in ["user", "assistant", "system"]:
            print(f"[ERROR] Invalid message_type: {message_type}")
            return {"status": "error", "message": f"Invalid message_type: {message_type}. Must be user/assistant/system"}
        
        if detected_intent and (not isinstance(detected_intent, str) or len(detected_intent) > 100):
            print(f"[ERROR] Detected intent must be a string with max length 100")
            return {"status": "error", "message": "Detected intent must be a string with max length 100"}
        
        try:
            if use_dev_store():
                new_message = await dev_add_message(session_id, user_id, message, message_type, detected_intent)
            else:
                await get_prisma()
                new_message = await prisma.chat_messages.create(
                    data={
                        "session_id": session_id,
                        "message": message,
                        "message_type": message_type,
                        "user_id": user_id,
                        "detected_intent": detected_intent
                    }
                )
            print(f"[LOG] Message saved for session {session_id}")
        except Exception as e:
            print(f"[ERROR] Failed to save message: {e}")
            return {"status": "error", "message": f"Failed to save message: {str(e)}"}
        
        # Store message in Redis (best-effort — may fail if Redis is not configured)
        try:
            result = await add_message_to_chat(session_id, message, message_type, detected_intent)
            if result.get("status") == "error":
                print(f"[WARNING] Failed to store message in Redis: {result.get('message')}")
        except Exception as redis_err:
            print(f"[WARNING] Redis store skipped: {redis_err}")
        
        print(f"[LOG] Message successfully added for session {session_id}")
        await invalidate_session_details_cache(session_id, user_id)
        return {"status": "success", "message": "Message added", "message_id": new_message["id"] if isinstance(new_message, dict) else new_message.id}
    
    except Exception as e:
        print(f"[ERROR] Unexpected error in add_chats: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": f"Failed to add message: {str(e)}"}
