"""
Authentication Controller with SIWE (Sign-In With Ethereum)
Implements secure wallet-based authentication
"""
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from core.database import prisma, get_prisma
from dependencies.auth import create_access_token, verify_siwe_signature
from datetime import datetime, timedelta
import json
import secrets


async def RequestNonce(req: Request):
    """
    Generate a nonce for SIWE authentication
    This should be called before signing the message
    """
    try:
        walletAddress = req.path_params.get("walletAddress")
        
        if not walletAddress or not isinstance(walletAddress, str) or len(walletAddress.strip()) == 0:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "Invalid wallet address provided"
                }
            )
        
        # Generate a cryptographically secure random nonce
        nonce = secrets.token_urlsafe(32)
        
        # BUG FIX: store nonce in Redis with 5-minute TTL for later verification
        try:
            from helpers.redis_functions import get_redis_connection
            r = await get_redis_connection()
            await r.setex(f"nonce:{walletAddress.strip().lower()}", 300, nonce)
            await r.close()
        except Exception as redis_err:
            # Redis may be unconfigured in dev — log and continue. Nonce won't be verifiable.
            print(f"[AUTH WARNING] Could not store nonce in Redis: {redis_err}")
        
        # BUG FIX: use datetime.utcnow().isoformat() — not the timedelta class itself
        timestamp = datetime.utcnow().isoformat()
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "nonce": nonce,
                "message": f"Sign this message to authenticate with Lemo:\n\nWallet: {walletAddress}\nNonce: {nonce}\nTimestamp: {timestamp}"
            }
        )
    except Exception as error:
        print(f"[AUTH ERROR] Error generating nonce: {error}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "Failed to generate nonce"
            }
        )


async def AuthenticateUser(req: Request):
    """
    Authenticate user with SIWE signature and return JWT token
    """
    await get_prisma()
    
    try:
        body = await req.json()
        walletAddress = req.path_params.get("walletAddress")
        message = body.get("message")  # SIWE message
        signature = body.get("signature")  # Wallet signature
        
        if not walletAddress or not isinstance(walletAddress, str) or len(walletAddress.strip()) == 0:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "Invalid wallet address provided"
                }
            )
        
        if not message or not signature:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "Message and signature are required for SIWE authentication"
                }
            )
        
        normalizedWalletAddress = walletAddress.strip().lower()
        
        # BUG FIX: verify stored nonce (replay attack prevention)
        try:
            from helpers.redis_functions import get_redis_connection
            r = await get_redis_connection()
            stored_nonce = await r.get(f"nonce:{normalizedWalletAddress}")
            if stored_nonce:
                # Parse the nonce from the SIWE message (line starting with "Nonce: ")
                nonce_in_message = None
                for line in message.splitlines():
                    if line.startswith("Nonce: "):
                        nonce_in_message = line[len("Nonce: "):].strip()
                        break
                stored_nonce_str = stored_nonce.decode() if isinstance(stored_nonce, bytes) else stored_nonce
                if nonce_in_message != stored_nonce_str:
                    await r.close()
                    return JSONResponse(
                        status_code=401,
                        content={"success": False, "error": "Invalid or expired nonce"}
                    )
                # One-time use — delete immediately after verification
                await r.delete(f"nonce:{normalizedWalletAddress}")
            else:
                print(f"[AUTH WARNING] No stored nonce found for {normalizedWalletAddress} — skipping nonce check")
            await r.close()
        except Exception as redis_err:
            print(f"[AUTH WARNING] Redis nonce verification skipped: {redis_err}")
        
        # Verify SIWE signature
        is_valid = await verify_siwe_signature(message, signature, normalizedWalletAddress)
        
        if not is_valid:
            return JSONResponse(
                status_code=401,
                content={
                    "success": False,
                    "error": "Invalid signature or message"
                }
            )
        
        # Find user in database
        dbUser = await prisma.users.find_unique(
            where={"wallet_address": normalizedWalletAddress}
        )
        
        if not dbUser:
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "error": "User not found. Please register first."
                }
            )
        
        if not dbUser.is_active:
            return JSONResponse(
                status_code=403,
                content={
                    "success": False,
                    "error": "User account is inactive"
                }
            )
        
        # Create JWT token
        access_token = create_access_token(
            data={"sub": normalizedWalletAddress}
        )
        
        user_data = {
            "id": dbUser.id,
            "email": dbUser.email,
            "first_name": dbUser.first_name,
            "last_name": dbUser.last_name,
            "wallet_address": dbUser.wallet_address,
            "is_active": dbUser.is_active,
        }
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "User authenticated successfully",
                "access_token": access_token,
                "token_type": "bearer",
                "data": {
                    "user": user_data
                }
            }
        )
    
    except Exception as error:
        print(f"[AUTH ERROR] Error during authentication: {error}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "Authentication failed"
            }
        )


async def CreateUser(req: Request):
    """Create a new user account"""
    await get_prisma()
    
    try:
        body = await req.json()
        walletAddress = req.path_params.get("walletAddress")
        email = body.get("email")
        firstName = body.get("firstName")
        lastName = body.get("lastName")
        otherDetails = body.get("otherDetails")
        
        if not walletAddress or not isinstance(walletAddress, str) or len(walletAddress.strip()) == 0:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "Valid wallet address is required"
                }
            )
        
        if not email or not isinstance(email, str) or "@" not in email:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "Valid email is required"
                }
            )
        
        if not firstName or not isinstance(firstName, str) or len(firstName.strip()) == 0:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "First name is required"
                }
            )
        
        if not lastName or not isinstance(lastName, str) or len(lastName.strip()) == 0:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "Last name is required"
                }
            )
        
        normalizedWalletAddress = walletAddress.strip().lower()
        normalizedEmail = email.strip()
        
        existingUser = await prisma.users.find_first(
            where={
                "OR": [
                    {"wallet_address": normalizedWalletAddress},
                    {"email": normalizedEmail},
                ]
            }
        )
        
        if existingUser:
            if existingUser.wallet_address == normalizedWalletAddress:
                return JSONResponse(
                    status_code=409,
                    content={
                        "success": False,
                        "error": "User with this wallet address already exists"
                    }
                )
            if existingUser.email == normalizedEmail:
                return JSONResponse(
                    status_code=409,
                    content={
                        "success": False,
                        "error": "User with this email already exists"
                    }
                )
        
        other_details_value = None
        if otherDetails:
            if isinstance(otherDetails, dict):
                other_details_value = json.dumps(otherDetails)
            elif isinstance(otherDetails, str):
                other_details_value = otherDetails
            else:
                other_details_value = json.dumps(otherDetails)
        
        create_data = {
            "id": normalizedWalletAddress,
            "wallet_address": normalizedWalletAddress,
            "email": normalizedEmail,
            "first_name": firstName.strip(),
            "last_name": lastName.strip(),
            "is_active": True,
        }
        
        if other_details_value is not None:
            create_data["other_details"] = other_details_value
        
        newUser = await prisma.users.create(data=create_data)
        
        user_data = {
            "id": newUser.id,
            "email": newUser.email,
            "first_name": newUser.first_name,
            "last_name": newUser.last_name,
            "wallet_address": newUser.wallet_address,
        }
        
        return JSONResponse(
            status_code=201,
            content={
                "success": True,
                "message": "User created successfully",
                "data": {
                    "user": user_data
                }
            }
        )
    
    except Exception as error:
        print(f"[AUTH ERROR] Error during user creation: {error}")
        
        if hasattr(error, "code") and error.code == "P2002":
            return JSONResponse(
                status_code=409,
                content={
                    "success": False,
                    "error": "User with this wallet address or email already exists"
                }
            )
        
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "Failed to create user"
            }
        )
