import base64
import os
import secrets
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.database import get_db


class BasicAuthMiddleware(BaseHTTPMiddleware):
    """HTTP Basic Auth middleware for protecting the app."""

    # Paths that don't require auth (health checks for Cloud Run)
    PUBLIC_PATHS = {"/api/health"}
    # Paths that use scheduler secret instead of basic auth
    INTERNAL_PREFIX = "/api/internal/"

    # Rate limiting: max failed attempts per IP before lockout
    MAX_FAILED_ATTEMPTS = 5
    LOCKOUT_SECONDS = 300  # 5 minutes

    def __init__(self, app):
        super().__init__(app)
        # Track failed attempts: {ip: [(timestamp, ...), ...]}
        self._failed_attempts: dict[str, list[float]] = defaultdict(list)

    def _is_rate_limited(self, client_ip: str) -> bool:
        """Check if an IP is locked out due to too many failed attempts."""
        now = time.monotonic()
        # Remove expired entries
        self._failed_attempts[client_ip] = [
            t for t in self._failed_attempts[client_ip]
            if now - t < self.LOCKOUT_SECONDS
        ]
        return len(self._failed_attempts[client_ip]) >= self.MAX_FAILED_ATTEMPTS

    def _record_failure(self, client_ip: str):
        self._failed_attempts[client_ip].append(time.monotonic())

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip auth for public health endpoint
        if path in self.PUBLIC_PATHS:
            return await call_next(request)

        # Skip auth for internal endpoints (they use X-Scheduler-Secret)
        if path.startswith(self.INTERNAL_PREFIX):
            return await call_next(request)

        # Skip if auth not configured (local development)
        if not settings.auth_enabled:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"

        # Check rate limit before processing credentials
        if self._is_rate_limited(client_ip):
            return Response(
                content="Too many failed attempts. Try again later.",
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": str(self.LOCKOUT_SECONDS)},
            )

        # Check Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Basic "):
            try:
                credentials = base64.b64decode(auth_header[6:]).decode("utf-8")
                username, password = credentials.split(":", 1)

                # Use secrets.compare_digest to prevent timing attacks
                username_ok = secrets.compare_digest(username, settings.auth_username)
                password_ok = secrets.compare_digest(password, settings.auth_password)

                if username_ok and password_ok:
                    return await call_next(request)
            except (ValueError, UnicodeDecodeError):
                pass

        # Auth failed - record and return 401
        self._record_failure(client_ip)
        return Response(
            content="Authentication required",
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": 'Basic realm="Danecast Trades"'},
        )

# Static files directory (frontend build)
STATIC_DIR = Path(__file__).parent.parent / "static"

from app.routes import (
    watchlist_router,
    price_targets_router,
    journal_router,
    scanner_router,
    alerts_router,
    internal_router,
    dashboard_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown


app = FastAPI(
    title="Danecast Trades API",
    version="0.1.0",
    lifespan=lifespan,
)

# Basic auth middleware (production security)
app.add_middleware(BasicAuthMiddleware)

# CORS: Only needed for local development (cross-origin requests from Vite dev server)
# In production, frontend is served from same origin, so CORS is not needed
if settings.environment == "development":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],  # Vite dev server
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(watchlist_router)
app.include_router(price_targets_router)
app.include_router(journal_router)
app.include_router(scanner_router)
app.include_router(alerts_router)
app.include_router(internal_router)
app.include_router(dashboard_router)


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}


@app.get("/api/health/db")
async def health_check_db(db: AsyncSession = Depends(get_db)):
    """Database health check. Protected by basic auth (not in PUBLIC_PATHS)."""
    result = await db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}


# Serve static frontend in production
if STATIC_DIR.exists():
    # Mount static assets (JS, CSS, etc.) if directory exists
    assets_dir = STATIC_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    # Catch-all route for client-side routing (must be last)
    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str):
        # API routes are handled by their routers - if we get here for /api/*, it's a 404
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")

        # Serve index.html for all other routes (SPA client-side routing)
        index_path = STATIC_DIR / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        raise HTTPException(status_code=404, detail="Frontend not built")
