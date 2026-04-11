# routes/sessions.py
from fastapi import APIRouter, Request, Depends
from controllers.sessions import save_message, create_session, get_session, get_all_sessions
from dependencies.auth import get_current_user  # Changed import

router = APIRouter()

@router.post('/')
async def create_session_route(request: Request, user = Depends(get_current_user)):
    # User is already authenticated, set it in request.state
    request.state.user_id = user.id
    return await create_session(request)

@router.get('/')
async def get_all_sessions_route(request: Request, user = Depends(get_current_user)):
    request.state.user_id = user.id
    return await get_all_sessions(request)

@router.get('/data')
async def get_session_route(request: Request, user = Depends(get_current_user)):
    request.state.user_id = user.id
    return await get_session(request)

@router.post('/message')
async def save_message_route(request: Request, user = Depends(get_current_user)):
    request.state.user_id = user.id
    return await save_message(request)