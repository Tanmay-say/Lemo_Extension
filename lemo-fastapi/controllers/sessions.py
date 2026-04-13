# controllers/sessions.py
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from core.database import prisma, get_prisma
from helpers.dev_store import (
    add_message as dev_add_message,
    create_session as dev_create_session,
    get_session_with_messages as dev_get_session_with_messages,
    list_sessions as dev_list_sessions,
    use_dev_store,
)


async def save_message(req: Request):
    """Save a chat message to the database"""
    try:
        # Get userId from request state (set by middleware/dependency)
        user_id = req.state.user_id
        
        # Get request body
        body = await req.json()
        session_id = body.get("session_id")
        message = body.get("message")
        message_type = body.get("message_type")
        detected_intent = body.get("detected_intent")
        
        # Validation
        if not session_id or not message or not message_type:
            return JSONResponse(
                status_code=400,
                content={"error": "Session ID, message, and message type are required"}
            )
        
        if message_type not in ["user", "assistant", "system"]:
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid message type"}
            )
        
        if detected_intent and (not isinstance(detected_intent, str) or len(detected_intent) > 100):
            return JSONResponse(
                status_code=400,
                content={"error": "Detected intent must be a string"}
            )
        
        if use_dev_store():
            try:
                new_message = await dev_add_message(session_id, user_id, message, message_type, detected_intent)
            except ValueError:
                return JSONResponse(status_code=403, content={"error": "Session not found or unauthorized"})
        else:
            await get_prisma()
            session = await prisma.chat_sessions.find_first(where={"id": session_id, "user_id": user_id})
            if not session:
                return JSONResponse(status_code=403, content={"error": "Session not found or unauthorized"})
            new_message = await prisma.chat_messages.create(
                data={
                    "session_id": session_id,
                    "message": message,
                    "message_type": message_type,
                    "user_id": user_id,
                    "detected_intent": detected_intent
                }
            )
        
        return JSONResponse(
            status_code=201,
            content={
                "message": "Message saved successfully",
                "message_id": new_message["id"] if isinstance(new_message, dict) else new_message.id
            }
        )
        
    except Exception as error:
        print(f"[ERROR] Error saving message: {str(error)}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error"}
        )


async def create_session(req: Request):
    """Create a new chat session"""
    try:
        # Get userId from request state
        user_id = req.state.user_id
        
        # Get request body
        body = await req.json()
        current_url = body.get("current_url")
        current_domain = body.get("current_domain")
        
        # Validation
        if not current_url or not current_domain:
            return JSONResponse(
                status_code=400,
                content={"error": "Current URL and domain are required"}
            )
        
        # Validate field lengths based on schema constraints
        if len(current_domain) > 255:
            return JSONResponse(
                status_code=400,
                content={"error": "Domain is too long. Maximum length is 255 characters"}
            )
        
        if use_dev_store():
            session = await dev_create_session(user_id, current_url, current_domain)
        else:
            await get_prisma()
            session = await prisma.chat_sessions.create(
                data={
                    "user_id": user_id,
                    "current_url": current_url,
                    "current_domain": current_domain
                }
            )
        
        return JSONResponse(
            status_code=201,
            content={
                "message": "Session created successfully",
                "session_id": session["id"] if isinstance(session, dict) else session.id
            }
        )
        
    except Exception as error:
        print(f"[ERROR] Error creating session: {str(error)}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error"}
        )

async def get_session(req: Request):
    """Get a session with its messages"""
    try:
        user_id = req.state.user_id
        
        session_id = req.query_params.get("id")
        current_url = req.query_params.get("current_url")
        current_domain = req.query_params.get("current_domain")
        
        if not session_id and not current_domain and not current_url:
            raise HTTPException(
                status_code=400,
                detail="At least one parameter is required: id, current_domain, or current_url"
            )
        
        where_clause = {"user_id": user_id}
        
        if session_id:
            where_clause["id"] = session_id
        elif current_domain:
            where_clause["current_domain"] = current_domain
        elif current_url:
            where_clause["current_url"] = current_url
        
        if use_dev_store():
            if session_id:
                session = await dev_get_session_with_messages(session_id, user_id)
            else:
                session = None
                for item in await dev_list_sessions(user_id):
                    if current_domain and item.get("current_domain") == current_domain:
                        session = await dev_get_session_with_messages(item["id"], user_id)
                        break
                    if current_url and item.get("current_url") == current_url:
                        session = await dev_get_session_with_messages(item["id"], user_id)
                        break
        else:
            await get_prisma()
            session = await prisma.chat_sessions.find_first(
                where=where_clause,
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
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Return dict directly - FastAPI handles datetime serialization
        return {"session": session if isinstance(session, dict) else session.model_dump(mode='json')}
        
    except HTTPException:
        raise
    except Exception as error:
        print(f"[ERROR] Error getting session: {str(error)}")
        raise HTTPException(status_code=500, detail="Internal server error")


async def get_all_sessions(req: Request):
    """Get all sessions for a user"""
    try:
        user_id = req.state.user_id
        if use_dev_store():
            return {"sessions": await dev_list_sessions(user_id)}
        await get_prisma()
        sessions = await prisma.chat_sessions.find_many(where={"user_id": user_id})
        return {"sessions": [session.model_dump(mode='json') for session in sessions]}
        
    except Exception as error:
        print(f"[ERROR] Error getting sessions: {str(error)}")
        raise HTTPException(status_code=500, detail="Internal server error")
