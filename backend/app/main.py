import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db

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
    result = await db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected", "result": result.scalar()}


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
