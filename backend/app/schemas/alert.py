from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AlertCondition(BaseModel):
    """Structured alert condition for validation."""

    metric: str = Field(..., description="Metric to check: price, rsi, hv_rank, eps, etc.")
    operator: str = Field(..., pattern="^(>|>=|<|<=|==)$")
    value: float = Field(..., description="Target value to compare against")
    trigger_date: Optional[str] = Field(
        default=None, description="For earnings_check: date to evaluate"
    )


class AlertCreate(BaseModel):
    watchlist_id: Optional[UUID] = None
    ticker: str = Field(..., max_length=10)
    name: str = Field(..., max_length=100)
    alert_type: str = Field(
        ...,
        pattern="^(price_cross|earnings_check|date_reminder|technical_signal|custom)$",
    )
    condition: dict[str, Any] = Field(
        ..., description="JSONB condition: {metric, operator, value, ...}"
    )
    action_note: Optional[str] = None
    priority: str = Field(default="normal", pattern="^(low|normal|high|urgent)$")
    expires_at: Optional[datetime] = None

    @field_validator("condition")
    @classmethod
    def validate_condition(cls, v: dict) -> dict:
        """Ensure condition has required fields."""
        if "metric" not in v:
            raise ValueError("condition must include 'metric'")
        if "operator" not in v:
            raise ValueError("condition must include 'operator'")
        if "value" not in v:
            raise ValueError("condition must include 'value'")
        if v["operator"] not in (">", ">=", "<", "<=", "=="):
            raise ValueError("operator must be one of: >, >=, <, <=, ==")
        return v


class AlertUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=100)
    condition: Optional[dict[str, Any]] = None
    action_note: Optional[str] = None
    status: Optional[str] = Field(
        default=None, pattern="^(active|triggered|dismissed|expired)$"
    )
    priority: Optional[str] = Field(default=None, pattern="^(low|normal|high|urgent)$")
    expires_at: Optional[datetime] = None

    @field_validator("condition")
    @classmethod
    def validate_condition(cls, v: Optional[dict]) -> Optional[dict]:
        if v is None:
            return v
        if "metric" not in v:
            raise ValueError("condition must include 'metric'")
        if "operator" not in v:
            raise ValueError("condition must include 'operator'")
        if "value" not in v:
            raise ValueError("condition must include 'value'")
        if v["operator"] not in (">", ">=", "<", "<=", "=="):
            raise ValueError("operator must be one of: >, >=, <, <=, ==")
        return v


class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    watchlist_id: Optional[UUID]
    ticker: str
    name: str
    alert_type: str
    condition: dict[str, Any]
    action_note: Optional[str]
    status: str
    priority: str
    triggered_at: Optional[datetime]
    expires_at: Optional[datetime]
    created_at: datetime


class AlertHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    alert_id: UUID
    evaluated_at: datetime
    condition_met: bool
    actual_value: Optional[Decimal]
    notification_sent: bool
    notes: Optional[str]


class AlertEvaluateRequest(BaseModel):
    """Request to manually evaluate alerts (for testing)."""

    alert_type: Optional[str] = Field(
        default=None,
        pattern="^(price_cross|earnings_check|date_reminder|technical_signal|custom)$",
        description="Filter to specific alert type, or evaluate all if not specified",
    )


class AlertEvaluateResponse(BaseModel):
    """Response from alert evaluation."""

    evaluated: int
    triggered: int
    notifications_sent: int
