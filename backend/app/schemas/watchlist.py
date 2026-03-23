from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WatchlistItemCreate(BaseModel):
    ticker: str = Field(..., max_length=10)
    status: str = Field(default="watching", pattern="^(watching|position_open|closed)$")
    position_type: Optional[str] = Field(
        default=None, pattern="^(long|short|cash_secured_put|covered_call)$"
    )
    entry_price: Optional[Decimal] = None
    entry_date: Optional[date] = None
    shares_or_contracts: Optional[int] = None
    cost_basis: Optional[Decimal] = None
    tags: list[str] = Field(default_factory=list)


class WatchlistItemUpdate(BaseModel):
    ticker: Optional[str] = Field(default=None, max_length=10)
    status: Optional[str] = Field(
        default=None, pattern="^(watching|position_open|closed)$"
    )
    position_type: Optional[str] = Field(
        default=None, pattern="^(long|short|cash_secured_put|covered_call)$"
    )
    entry_price: Optional[Decimal] = None
    entry_date: Optional[date] = None
    shares_or_contracts: Optional[int] = None
    cost_basis: Optional[Decimal] = None
    sort_order: Optional[int] = None
    tags: Optional[list[str]] = None


class WatchlistItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ticker: str
    status: str
    position_type: Optional[str]
    entry_price: Optional[Decimal]
    entry_date: Optional[date]
    shares_or_contracts: Optional[int]
    cost_basis: Optional[Decimal]
    sort_order: int
    tags: Optional[list[str]]
    created_at: datetime
    updated_at: datetime


class WatchlistReorderRequest(BaseModel):
    """Request body for bulk reordering watchlist items."""
    items: list[UUID] = Field(..., description="List of item IDs in desired order")
