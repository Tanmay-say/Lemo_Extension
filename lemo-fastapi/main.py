import logging
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from controllers.query_handler import query_handler
from agents.graph import pipeline_backend_name
from core.config import (
    chat_model_name,
    gemini_embed_model,
    gemini_fast_model,
    get_llm_keys,
    llm_provider_preference,
)
from core.logging_config import request_id_middleware, setup_logging
from routes.authentication_routes import router as authentication_routes
from routes.session_routes import router as session_routes

setup_logging()
logger = logging.getLogger("lemo.main")


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

    logger.info("=" * 80)
    logger.info("[LEMO] Starting Lemo FastAPI Server")
    logger.info("=" * 80)
    logger.info("[OK] Rate limiting enabled")
    logger.info("[OK] SIWE authentication configured")
    logger.info("[OK] ScrapingBee scraper ready")
    logger.info("[OK] LLM providers configured: %s", provider_summary)
    logger.info("[OK] LLM provider preference: %s", llm_provider_preference())
    logger.info("[OK] Python executable: %s", sys.executable)
    logger.info("[OK] Pipeline backend: %s", pipeline_backend_name())
    logger.info(
        "[OK] Models -> pro=%s fast=%s embed=%s",
        chat_model_name("gemini"),
        gemini_fast_model(),
        gemini_embed_model(),
    )
    if os.getenv("UVICORN_RELOAD") == "true":
        logger.info("[INFO] Development reload is enabled; startup logs can appear more than once")
    logger.info("=" * 80)
    yield
    logger.info("Shutting down Lemo FastAPI Server...")


app = FastAPI(lifespan=lifespan)

app.middleware("http")(request_id_middleware)

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
        },
        "runtime": {
            "python": sys.executable,
            "pipeline_backend": pipeline_backend_name(),
        },
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
