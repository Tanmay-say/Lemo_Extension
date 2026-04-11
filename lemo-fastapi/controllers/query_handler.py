from fastapi import Request, Depends
from fastapi.responses import JSONResponse
from helpers.intent_detection import intent_detection
from cases.asking import asking, current_page_asking
from helpers.get_session_details import get_session_details
from helpers.add_chats import add_chats
from dependencies.auth import get_optional_user
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def query_handler(request: Request):
    """
    Handle user queries with proper error handling and rate limiting
    """
    try:
        session_id = request.query_params.get("session_id")
        body = await request.json()
        
        # Get user from JWT token (optional - works for both authenticated and anonymous)
        user = await get_optional_user(request)
        user_id = user.wallet_address if user else request.headers.get("Authorization")
        
        if not session_id:
            return JSONResponse(
                content={"success": False, "message": "Session ID is required"}, 
                status_code=400
            )
        
        if not user_id:
            return JSONResponse(
                content={"success": False, "message": "User authentication required"}, 
                status_code=401
            )
        
        session_details = await get_session_details(session_id, user_id)
        user_query = body.get("user_query")
        
        if not user_query:
            return JSONResponse(
                content={"success": False, "message": "User query is required"}, 
                status_code=400
            )
        
        domain = session_details.get("current_domain")
        current_page_url = session_details.get("current_url")
        
        if not current_page_url:
            return JSONResponse(
                content={"success": False, "message": "Current page URL not found in session"}, 
                status_code=400
            )

        # Detect intent (now properly awaited — was blocking the event loop)
        intent = await intent_detection(user_query)
        logger.info(f"Detected intent: {intent.intent}, scope: {intent.scope}")
        
        # Process based on intent
        answer = None
        
        if intent.scope == "current_page":
            logger.info("Processing current_page intent")
            answer = await current_page_asking(user_query, current_page_url)
        else:
            logger.info(f"Processing {intent.scope} intent")
            # Build formatted chat history text for chat_history scope
            chat_history = "\n".join([
                f"{msg.get('message_type')}: {msg.get('message')}" 
                for msg in session_details.get("chat_messages", [])
            ])
            # BUG FIX: pass chat_history (formatted text), not session_id
            answer = await asking(user_query, domain, current_page_url, intent.scope, session_id, chat_history)
        
        logger.info(f"Generated answer: {answer[:100] if answer else 'None'}...")
        
        # Add messages to both DB and Redis
        await add_chats(session_id, user_query, "user", intent.intent, user_id)
        if answer:
            await add_chats(session_id, answer, "assistant", intent.intent, user_id)
        
        return JSONResponse(
            content={"success": True, "answer": answer}, 
            status_code=200
        )
    
    except ValueError as e:
        logger.error(f"ValueError in query_handler: {e}")
        return JSONResponse(
            content={"success": False, "message": "Invalid request data"}, 
            status_code=400
        )
    except Exception as e:
        logger.error(f"Unexpected error in query_handler: {e}", exc_info=True)
        # Never expose internal error details to users
        return JSONResponse(
            content={"success": False, "message": "An error occurred processing your request"}, 
            status_code=500
        )
