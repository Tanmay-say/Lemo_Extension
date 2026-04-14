from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from controllers.query_handler import query_handler
from core.config import get_llm_keys, llm_provider_preference
from routes.authentication_routes import router as authentication_routes
from routes.session_routes import router as session_routes
import os


# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager (replaces deprecated @app.on_event)."""
    # Startup
    llm_keys = get_llm_keys()
    configured_providers = []
    if llm_keys.gemini:
        configured_providers.append("Gemini")
    if llm_keys.emergent:
        configured_providers.append("Emergent")
    provider_summary = ", ".join(configured_providers) if configured_providers else "none"

    print("="*80)
    print("🚀 Starting Lemo FastAPI Server")
    print("="*80)
    print("✓ Rate limiting enabled")
    print("✓ SIWE authentication configured")
    print("✓ ScrapingBee scraper ready")
    print(f"✓ LLM providers configured: {provider_summary}")
    print(f"✓ LLM provider preference: {llm_provider_preference()}")
    if os.getenv("UVICORN_RELOAD") == "true":
        print("ℹ Development reload is enabled; startup logs can appear more than once")
    print("="*80)
    yield
    # Shutdown
    print("Shutting down Lemo FastAPI Server...")


app = FastAPI(lifespan=lifespan)

# Add rate limiter to app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS Configuration
# BUG FIX: allow_credentials=True + allow_origins=["*"] is rejected by browsers.
# Using allow_credentials=False keeps wildcard origins valid for dev.
# For production with auth headers/cookies, replace "*" with explicit origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {
        "message": "Lemo AI Shopping Assistant API",
        "version": "2.0.0",
        "features": {
            "authentication": "SIWE + JWT",
            "scraping": "ScrapingBee + httpx async",
            "llm": "Gemini + Emergent LLM Key support",
            "rate_limiting": "Enabled"
        }
    }


@app.post("/query")
@limiter.limit(f"{os.getenv('RATE_LIMIT_PER_MINUTE', '60')}/minute")
async def query(request: Request):
    """
    Process user query with rate limiting
    Rate limit: 60 requests per minute per IP (configurable via RATE_LIMIT_PER_MINUTE env var)
    """
    return await query_handler(request)


# Include routers
app.include_router(authentication_routes, prefix="/auth", tags=["Authentication"])
app.include_router(session_routes, prefix="/sessions", tags=["Sessions"])
