"""
FastAPI application entry point — Gene Summary API v1
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from core.config import get_settings
from core.logging_config import get_logger
from routers.gene import router as gene_router

logger = get_logger("main")
settings = get_settings()

# ── Rate limiter ──────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=[settings.rate_limit])


# ── Lifespan ─────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"{settings.app_name} v{settings.app_version} starting up")
    yield
    logger.info(f"{settings.app_name} shutting down")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Human Gene Summary API — UniProt-backed, Swiss-Prot canonical entries only. "
        "Strictly filtered to Homo sapiens (organism_id:9606)."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Rate-limit handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS (adjust origins as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(gene_router)

# Serve Frontend
if os.path.exists("frontend"):
    app.mount("/static", StaticFiles(directory="frontend"), name="static")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str):
        # Serve index.html for root or any non-API path
        if not full_path.startswith("api/"):
            return FileResponse("frontend/index.html")
        return JSONResponse(status_code=404, content={"error": "Not Found"})
else:
    @app.get("/", include_in_schema=False)
    async def root():
        return {
            "service": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
            "endpoints": [
                "GET /api/v1/gene/{symbol}",
                "GET /api/v1/gene/{symbol}/exists",
            ],
        }


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "version": settings.app_version}
