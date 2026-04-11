from fastapi import APIRouter, Request
from controllers.authentication import AuthenticateUser, CreateUser, RequestNonce

router = APIRouter()

@router.get("/nonce/{walletAddress}")
async def request_nonce(req: Request):
    """Get a nonce for SIWE authentication"""
    return await RequestNonce(req)

@router.post("/login/{walletAddress}")
async def authenticate_user(req: Request):
    """Authenticate user with SIWE signature and get JWT token"""
    return await AuthenticateUser(req)

@router.post("/register/{walletAddress}")
async def create_user(req: Request):
    """Register a new user"""
    return await CreateUser(req)
