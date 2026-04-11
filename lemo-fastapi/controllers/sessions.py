# controllers/sessions.py
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from core.database import prisma, get_prisma


async def save_message(req: Request):
    """Save a chat message to the database"""
    await get_prisma()
    
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
        
        # SECURITY FIX: verify the session belongs to this user before writing
        session = await prisma.chat_sessions.find_first(
            where={"id": session_id, "user_id": user_id}
        )
        if not session:
            return JSONResponse(
                status_code=403,
                content={"error": "Session not found or unauthorized"}
            )
        
        # Create message
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
                "message_id": new_message.id
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
    await get_prisma()
    
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
        
        # Create session
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
                "session_id": session.id
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
    await get_prisma()
    
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
        return {"session": session.model_dump(mode='json')}
        
    except HTTPException:
        raise
    except Exception as error:
        print(f"[ERROR] Error getting session: {str(error)}")
        raise HTTPException(status_code=500, detail="Internal server error")


async def get_all_sessions(req: Request):
    """Get all sessions for a user"""
    await get_prisma()
    
    try:
        user_id = req.state.user_id
        
        sessions = await prisma.chat_sessions.find_many(
            where={"user_id": user_id}
        )
        
        # Return dict directly
        return {"sessions": [session.model_dump(mode='json') for session in sessions]}
        
    except Exception as error:
        print(f"[ERROR] Error getting sessions: {str(error)}")
        raise HTTPException(status_code=500, detail="Internal server error")