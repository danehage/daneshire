# CLAUDE.md — Backend

## Context

FastAPI backend serving the React frontend. All routes under `/api/`. Async SQLAlchemy 2.0 with Neon Postgres.

## Key patterns

### Database session

```python
# Always use this pattern for routes:
from app.database import get_session

@router.get("/api/watchlist")
async def list_watchlist(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(WatchlistItem).order_by(WatchlistItem.sort_order))
    return result.scalars().all()
```

### Model → Schema separation

SQLAlchemy models define the database. Pydantic schemas define API input/output. Never return a SQLAlchemy model directly from a route — always map to a response schema.

```python
# models/watchlist.py — database
class WatchlistItem(Base):
    __tablename__ = "watchlist_items"
    id = Column(UUID, primary_key=True, server_default=text("gen_random_uuid()"))
    ticker = Column(String(10), nullable=False)
    ...

# schemas/watchlist.py — API
class WatchlistItemCreate(BaseModel):
    ticker: str
    status: str = "watching"
    tags: list[str] = []

class WatchlistItemResponse(BaseModel):
    id: UUID
    ticker: str
    status: str
    tags: list[str]
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
```

### Service layer

Business logic lives in `services/`, not in routes. Routes handle HTTP concerns (parsing, validation, status codes). Services handle domain logic (scanning, scoring, alert evaluation).

```python
# routes/scanner.py — thin, delegates to service
@router.post("/api/scan/execute")
async def execute_scan(request: ScanRequest, session: AsyncSession = Depends(get_session)):
    scanner = ScannerService(session)
    scan_id = await scanner.start_scan(request.universe, request.filters)
    return {"scan_id": scan_id}

# services/scanner.py — contains actual logic
class ScannerService:
    async def start_scan(self, universe: str, filters: dict) -> UUID:
        ...
```

### Alert condition evaluation

Alert conditions are JSONB. The evaluator is a pure function:

```python
def evaluate_condition(condition: dict, market_data: dict) -> bool:
    """
    condition: {"metric": "price", "operator": ">", "value": 150}
    market_data: {"price": 155.30, "rsi": 42.1, "hv_rank": 68.0, ...}
    """
    metric = condition["metric"]
    operator = condition["operator"]
    target = condition["value"]
    actual = market_data.get(metric)

    if actual is None:
        return False

    ops = {">": gt, ">=": ge, "<": lt, "<=": le, "==": eq}
    return ops[operator](actual, target)
```

Write tests for this function before building the alert engine.

## Environment variables

```
NEON_DATABASE_URL=postgresql+asyncpg://user:pass@host/dbname?sslmode=require
FMP_API_KEY=your_key
PUSHOVER_USER_KEY=your_user_key
PUSHOVER_API_TOKEN=your_app_token
SCHEDULER_SECRET=a_random_string_for_cron_auth
ENVIRONMENT=development  # development | production
```

## Testing

- Use `pytest` + `pytest-asyncio`
- Test files mirror source structure: `tests/test_routes/test_watchlist.py`
- Use an in-memory or test-specific Neon branch for database tests
- Alert condition evaluator should have the most thorough test coverage
- Scanner tests can mock the FMP API client

## Dependencies (pin these)

```
fastapi==0.115.*
uvicorn[standard]==0.34.*
sqlalchemy[asyncio]==2.0.*
asyncpg==0.30.*
alembic==1.14.*
pydantic==2.10.*
pydantic-settings==2.7.*
httpx==0.28.*
pandas==2.2.*
numpy==2.1.*
python-dotenv==1.0.*
```
