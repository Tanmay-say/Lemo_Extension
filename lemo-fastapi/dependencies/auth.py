"""
SIWE (Sign-In With Ethereum) Authentication Middleware
Implements proper wallet-based authentication with signature verification
"""
from fastapi import Request, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from datetime import datetime, timedelta
from types import SimpleNamespace

from core.database import prisma
from core.config import jwt_secret_key
from helpers.dev_store import get_user, use_dev_store
from siwe import SiweMessage


JWT_SECRET_KEY = jwt_secret_key()
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 1440

security = HTTPBearer()


def create_access_token(data: dict, expires_delta: timedelta = None):
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


async def verify_siwe_signature(message: str, signature: str, wallet_address: str) -> bool:
    """
    Verify SIWE signature
    
    Args:
        message: The SIWE message that was signed
        signature: The signature from the wallet
        wallet_address: The claimed wallet address
        
    Returns:
        True if signature is valid, False otherwise
    """
    try:
        # Parse SIWE message
        siwe_message = SiweMessage.from_message(message=message)
        
        # Verify the message was signed by the claimed address
        siwe_message.verify(signature=signature)
        
        # Check that the wallet address matches
        if siwe_message.address.lower() != wallet_address.lower():
            return False
        
        # Check message hasn't expired
        if siwe_message.expiration_time:
            if datetime.fromisoformat(siwe_message.expiration_time.replace('Z', '+00:00')) < datetime.now():
                return False
        
        return True
    except Exception as e:
        print(f"[AUTH] SIWE verification failed: {e}")
        return False


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Dependency to authenticate user via JWT token
    Replaces the insecure raw wallet address authentication
    """
    token = credentials.credentials
    
    try:
        # Decode JWT token
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        wallet_address: str = payload.get("sub")
        
        if wallet_address is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token"
            )
    except JWTError as e:
        print(f"[AUTH] JWT decode error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    if use_dev_store():
        user = await get_user(wallet_address)
        if user:
            return SimpleNamespace(**user)
        return SimpleNamespace(
            id=wallet_address,
            wallet_address=wallet_address,
            email="",
            first_name="",
            last_name="",
            is_active=True,
        )

    if not prisma.is_connected():
        await prisma.connect()

    user = await prisma.users.find_unique(where={"wallet_address": wallet_address})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive")
    return user


async def get_optional_user(request: Request):
    """
    Optional authentication - returns user if authenticated, None otherwise
    Useful for endpoints that work for both authenticated and anonymous users
    """
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return None
        
        token = auth_header.replace("Bearer ", "")
        
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        wallet_address: str = payload.get("sub")
        
        if wallet_address is None:
            return None

        if use_dev_store():
            user = await get_user(wallet_address)
            if user:
                return SimpleNamespace(**user)
            return SimpleNamespace(id=wallet_address, wallet_address=wallet_address, is_active=True)

        if not prisma.is_connected():
            await prisma.connect()

        user = await prisma.users.find_unique(where={"wallet_address": wallet_address})
        return user if user and user.is_active else None
    except Exception:
        return None
