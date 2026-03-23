from app.routes.watchlist import router as watchlist_router
from app.routes.price_targets import router as price_targets_router
from app.routes.journal import router as journal_router
from app.routes.scanner import router as scanner_router

__all__ = ["watchlist_router", "price_targets_router", "journal_router", "scanner_router"]
