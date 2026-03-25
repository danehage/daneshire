from app.routes.watchlist import router as watchlist_router
from app.routes.price_targets import router as price_targets_router
from app.routes.journal import router as journal_router
from app.routes.scanner import router as scanner_router
from app.routes.alerts import router as alerts_router
from app.routes.internal import router as internal_router
from app.routes.dashboard import router as dashboard_router

__all__ = [
    "watchlist_router",
    "price_targets_router",
    "journal_router",
    "scanner_router",
    "alerts_router",
    "internal_router",
    "dashboard_router",
]
