"""
Authentication Controller with SIWE (Sign-In With Ethereum)
Implements secure wallet-based authentication
"""
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from core.database import prisma, get_prisma
from dependencies.auth import create_access_token, verify_siwe_signature
from datetime import datetime, timezone, timedelta
from siwe import SiweMessage
import json
import secrets

from helpers.dev_store import create_or_update_user, get_user, use_dev_store


NONCE_TTL_SECONDS = 300


async def _store_nonce(wallet_address: str, nonce: str) -> None:
    from helpers.redis_functions import get_redis_connection

    r = await get_redis_connection()
    try:
        nonce_key = f"nonce:{wallet_address}"
        await r.sadd(nonce_key, nonce)
        await r.expire(nonce_key, NONCE_TTL_SECONDS)
    finally:
        await r.close()


async def _consume_nonce(wallet_address: str, nonce: str) -> bool:
    from helpers.redis_functions import get_redis_connection

    r = await get_redis_connection()
    try:
        nonce_key = f"nonce:{wallet_address}"
        is_valid = await r.sismember(nonce_key, nonce)
        if is_valid:
            await r.srem(nonce_key, nonce)
        return bool(is_valid)
    finally:
        await r.close()


async def GetUserStatus(req: Request):
    """Check whether a wallet address is registered and active."""
    try:
        walletAddress = req.path_params.get("walletAddress")
        if not walletAddress or not isinstance(walletAddress, str) or len(walletAddress.strip()) == 0:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Invalid wallet address provided"}
            )

        normalizedWalletAddress = walletAddress.strip().lower()

        if use_dev_store():
            dbUser = await get_user(normalizedWalletAddress)
        else:
            await get_prisma()
            dbUser = await prisma.users.find_unique(where={"wallet_address": normalizedWalletAddress})

        if not dbUser:
            return JSONResponse(
                status_code=404,
                content={"success": True, "exists": False, "is_active": False}
            )

        is_active = dbUser["is_active"] if isinstance(dbUser, dict) else dbUser.is_active
        user_data = {
            "id": dbUser["id"] if isinstance(dbUser, dict) else dbUser.id,
            "email": dbUser["email"] if isinstance(dbUser, dict) else dbUser.email,
            "first_name": dbUser["first_name"] if isinstance(dbUser, dict) else dbUser.first_name,
            "last_name": dbUser["last_name"] if isinstance(dbUser, dict) else dbUser.last_name,
            "wallet_address": dbUser["wallet_address"] if isinstance(dbUser, dict) else dbUser.wallet_address,
            "is_active": is_active,
        }

        if not is_active:
            return JSONResponse(
                status_code=403,
                content={"success": True, "exists": True, "is_active": False, "user": user_data}
            )

        return JSONResponse(
            status_code=200,
            content={"success": True, "exists": True, "is_active": True, "user": user_data}
        )

    except Exception as error:
        print(f"[AUTH ERROR] Error checking user status: {error}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "Failed to check user status"}
        )


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
        
        from web3 import Web3
        try:
            normalizedAddress = Web3.to_checksum_address(walletAddress.strip())
        except Exception:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "Invalid wallet address provided"
                }
            )

        # Generate a cryptographically secure random nonce (alphanumeric, min 8 chars per EIP-4361)
        nonce = secrets.token_hex(16)
        now = datetime.now(timezone.utc)
        expiry = now + timedelta(minutes=5)

        # Build a valid EIP-4361 SIWE message so the backend can verify it properly
        siwe_msg = SiweMessage(
            domain="localhost",
            address=normalizedAddress,
            statement="Sign in to Lemo AI Assistant",
            uri="http://localhost:8000",
            version="1",
            chain_id=11155111,  # Sepolia
            nonce=nonce,
            issued_at=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            expiration_time=expiry.strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        message_str = siwe_msg.prepare_message()

        # Store nonce in Redis with 5-minute TTL for replay-attack prevention.
        # Keep multiple valid nonces briefly to tolerate duplicate frontend auth flows.
        try:
            await _store_nonce(normalizedAddress.lower(), nonce)
        except Exception as redis_err:
            # Redis may be unconfigured in dev — log and continue.
            print(f"[AUTH WARNING] Could not store nonce in Redis: {redis_err}")
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "nonce": nonce,
                "message": message_str
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
        normalizedMessage = message.strip()
        try:
            parsed_message = SiweMessage.from_message(message=normalizedMessage)
        except Exception:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "Invalid SIWE message"
                }
            )
        
        # Verify stored nonce (replay attack prevention)
        try:
            nonce_in_message = parsed_message.nonce
            if nonce_in_message:
                nonce_ok = await _consume_nonce(normalizedWalletAddress, nonce_in_message)
                if not nonce_ok:
                    return JSONResponse(
                        status_code=401,
                        content={"success": False, "error": "Invalid or expired nonce"}
                    )
            else:
                return JSONResponse(
                    status_code=401,
                    content={"success": False, "error": "Invalid SIWE message nonce"}
                )
        except Exception as redis_err:
            print(f"[AUTH WARNING] Redis nonce verification skipped: {redis_err}")
        
        # Verify SIWE signature
        is_valid = await verify_siwe_signature(normalizedMessage, signature, normalizedWalletAddress)
        
        if not is_valid:
            return JSONResponse(
                status_code=401,
                content={
                    "success": False,
                    "error": "Invalid signature or message"
                }
            )
        
        if use_dev_store():
            dbUser = await get_user(normalizedWalletAddress)
            if not dbUser:
                return JSONResponse(
                    status_code=404,
                    content={"success": False, "error": "User not found. Please register first."}
                )
            if not dbUser.get("is_active", True):
                return JSONResponse(
                    status_code=403,
                    content={"success": False, "error": "User account is inactive"}
                )
        else:
            await get_prisma()
            dbUser = await prisma.users.find_unique(where={"wallet_address": normalizedWalletAddress})
            if not dbUser:
                return JSONResponse(
                    status_code=404,
                    content={"success": False, "error": "User not found. Please register first."}
                )
            if not dbUser.is_active:
                return JSONResponse(
                    status_code=403,
                    content={"success": False, "error": "User account is inactive"}
                )
        
        # Create JWT token
        access_token = create_access_token(
            data={"sub": normalizedWalletAddress}
        )
        
        user_data = {
            "id": dbUser["id"] if isinstance(dbUser, dict) else dbUser.id,
            "email": dbUser["email"] if isinstance(dbUser, dict) else dbUser.email,
            "first_name": dbUser["first_name"] if isinstance(dbUser, dict) else dbUser.first_name,
            "last_name": dbUser["last_name"] if isinstance(dbUser, dict) else dbUser.last_name,
            "wallet_address": dbUser["wallet_address"] if isinstance(dbUser, dict) else dbUser.wallet_address,
            "is_active": dbUser["is_active"] if isinstance(dbUser, dict) else dbUser.is_active,
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
        
        if use_dev_store():
            existingUser = await get_user(normalizedWalletAddress)
            if existingUser:
                return JSONResponse(
                    status_code=409,
                    content={"success": False, "error": "User with this wallet address already exists"}
                )
        else:
            await get_prisma()
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
        
        if use_dev_store():
            newUser = await create_or_update_user(
                normalizedWalletAddress,
                email=normalizedEmail,
                first_name=firstName.strip(),
                last_name=lastName.strip(),
                other_details=other_details_value,
            )
        else:
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
            "id": newUser["id"] if isinstance(newUser, dict) else newUser.id,
            "email": newUser["email"] if isinstance(newUser, dict) else newUser.email,
            "first_name": newUser["first_name"] if isinstance(newUser, dict) else newUser.first_name,
            "last_name": newUser["last_name"] if isinstance(newUser, dict) else newUser.last_name,
            "wallet_address": newUser["wallet_address"] if isinstance(newUser, dict) else newUser.wallet_address,
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
