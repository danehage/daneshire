"""
Scanner API routes with SSE streaming support.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.schemas.scan import (
    ScanRequest,
    ScanExecuteResponse,
    ScanResultItem,
    ScanResultsResponse,
    UniverseInfo,
)
from app.services import StockScanner, UNIVERSES, get_universe

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scan", tags=["scanner"])

# In-memory storage for active scans (replace with Redis/DB for production)
_active_scans: dict[str, dict] = {}


@router.get("/universes", response_model=list[UniverseInfo])
async def list_universes():
    """List available stock universes with their sizes."""
    descriptions = {
        "quick": "High volume, popular stocks for fast daily screening",
        "robinhood": "Most popular retail trading stocks",
        "sp500_sample": "100 representative large cap S&P 500 stocks",
        "sp500": "Full S&P 500 components (~500 stocks)",
    }

    return [
        UniverseInfo(
            name=name,
            size=len(tickers),
            description=descriptions.get(name, ""),
        )
        for name, tickers in UNIVERSES.items()
    ]


@router.post("/execute", response_model=ScanExecuteResponse)
async def execute_scan(request: ScanRequest):
    """
    Start a new scan. Returns scan_id to use for streaming progress.
    """
    tickers = get_universe(request.universe)
    if not tickers:
        raise HTTPException(status_code=400, detail=f"Unknown universe: {request.universe}")

    scanner = StockScanner()

    # Initialize scan state
    scan_state = {
        "status": "running",
        "universe": request.universe,
        "universe_size": len(tickers),
        "started_at": datetime.utcnow(),
        "progress": {"current": 0, "total": 0, "found": 0},
        "results": [],
        "scan_id": None,
    }

    async def progress_callback(event: dict):
        """Update scan state with progress."""
        if event["type"] == "progress":
            scan_state["progress"] = {
                "current": event["current"],
                "total": event["total"],
                "found": event["found"],
            }
        elif event["type"] == "complete":
            scan_state["status"] = "complete"

    # Run scan in background task
    async def run_scan():
        try:
            scan_id, results = await scanner.run_scan(
                tickers,
                progress_callback=progress_callback,
                use_cache=request.use_cache,
            )
            scan_state["scan_id"] = scan_id
            scan_state["results"] = results
            scan_state["status"] = "complete"
            scan_state["completed_at"] = datetime.utcnow()
        except Exception as e:
            logger.error(f"Scan failed: {e}")
            scan_state["status"] = "error"
            scan_state["error"] = str(e)

    # Start the scan task
    task = asyncio.create_task(run_scan())

    # Generate a temporary scan_id for tracking
    import uuid
    temp_scan_id = str(uuid.uuid4())
    scan_state["temp_id"] = temp_scan_id
    _active_scans[temp_scan_id] = scan_state

    return ScanExecuteResponse(
        scan_id=temp_scan_id,
        universe=request.universe,
        universe_size=len(tickers),
        message="Scan started. Use /stream endpoint for progress.",
    )


@router.get("/{scan_id}/stream")
async def stream_scan_progress(scan_id: str):
    """
    SSE endpoint for real-time scan progress.
    """
    if scan_id not in _active_scans:
        raise HTTPException(status_code=404, detail="Scan not found")

    async def event_generator() -> AsyncGenerator[str, None]:
        scan_state = _active_scans[scan_id]
        last_progress = None

        while True:
            current_progress = scan_state["progress"].copy()
            status = scan_state["status"]

            # Send progress update if changed
            if current_progress != last_progress:
                event = {
                    "type": "progress",
                    "scan_id": scan_id,
                    **current_progress,
                }
                yield f"data: {json.dumps(event)}\n\n"
                last_progress = current_progress

            # Send completion event
            if status == "complete":
                event = {
                    "type": "complete",
                    "scan_id": scan_id,
                    "total_analyzed": len(scan_state["results"]),
                }
                yield f"data: {json.dumps(event)}\n\n"
                break

            # Send error event
            if status == "error":
                event = {
                    "type": "error",
                    "scan_id": scan_id,
                    "error": scan_state.get("error", "Unknown error"),
                }
                yield f"data: {json.dumps(event)}\n\n"
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{scan_id}/results", response_model=ScanResultsResponse)
async def get_scan_results(scan_id: str):
    """
    Get results of a completed scan.
    """
    if scan_id not in _active_scans:
        raise HTTPException(status_code=404, detail="Scan not found")

    scan_state = _active_scans[scan_id]

    if scan_state["status"] == "running":
        raise HTTPException(status_code=202, detail="Scan still in progress")

    if scan_state["status"] == "error":
        raise HTTPException(status_code=500, detail=scan_state.get("error", "Scan failed"))

    return ScanResultsResponse(
        scan_id=scan_id,
        universe=scan_state["universe"],
        total_analyzed=len(scan_state["results"]),
        results=[ScanResultItem(**r) for r in scan_state["results"]],
        scanned_at=scan_state.get("completed_at", scan_state["started_at"]),
    )


@router.get("/ticker/{symbol}", response_model=ScanResultItem)
async def analyze_single_ticker(symbol: str):
    """
    Analyze a single ticker with full technical breakdown.
    """
    scanner = StockScanner()
    result = await scanner.analyze_ticker(symbol.upper())

    if not result:
        raise HTTPException(status_code=404, detail=f"Could not analyze {symbol}")

    return ScanResultItem(**result)
