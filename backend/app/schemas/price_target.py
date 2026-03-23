from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PriceTargetCreate(BaseModel):
    label: str = Field(..., max_length=50)
    price: Decimal
    direction: str = Field(default="below", pattern="^(above|below)$")
    alert_enabled: bool = False
    notes: Optional[str] = None


class PriceTargetUpdate(BaseModel):
    label: Optional[str] = Field(default=None, max_length=50)
    price: Optional[Decimal] = None
    direction: Optional[str] = Field(default=None, pattern="^(above|below)$")
    alert_enabled: Optional[bool] = None
    notes: Optional[str] = None


class PriceTargetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    watchlist_id: UUID
    label: str
    price: Decimal
    direction: str
    alert_enabled: bool
    triggered_at: Optional[datetime]
    notes: Optional[str]
    created_at: datetime
