from datetime import datetime
from decimal import Decimal
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    computed_field,
    model_validator,
)

from app.schemas.alert_conditions import condition_from_payload


AlertType = Literal[
    "price_cross",
    "earnings_check",
    "date_reminder",
    "technical_signal",
    "custom",
]
AlertStatus = Literal["active", "triggered", "dismissed", "expired"]
AlertPriority = Literal["low", "normal", "high", "urgent"]


class AlertCreate(BaseModel):
    watchlist_id: Optional[UUID] = None
    ticker: str = Field(..., max_length=10)
    name: str = Field(..., max_length=100)
    alert_type: AlertType
    condition: dict[str, Any] = Field(
        ..., description="Variant payload — validated against the typed Condition union"
    )
    action_note: Optional[str] = None
    priority: AlertPriority = "normal"
    expires_at: Optional[datetime] = None

    @model_validator(mode="after")
    def validate_condition_against_type(self) -> "AlertCreate":
        # Defer to the discriminated Condition union — operator allow-list,
        # required fields, and value coercion all live there.
        try:
            condition_from_payload(self.alert_type, self.condition)
        except ValidationError as exc:
            raise ValueError(
                f"Invalid condition for {self.alert_type}: {exc.errors()}"
            ) from exc
        return self


class AlertUpdate(BaseModel):
    """PATCH payload. ``condition`` is not validated here because the
    alert's existing ``alert_type`` is needed for dispatch — the route
    re-validates against the stored record."""

    name: Optional[str] = Field(default=None, max_length=100)
    condition: Optional[dict[str, Any]] = None
    action_note: Optional[str] = None
    status: Optional[AlertStatus] = None
    priority: Optional[AlertPriority] = None
    expires_at: Optional[datetime] = None


class AlertResponse(BaseModel):
    """Read model. ``formatted_condition`` is computed via the typed
    Condition's ``.format()`` so the UI and the notifier share one
    source of truth.
    """

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

    @computed_field  # type: ignore[prop-decorator]
    @property
    def formatted_condition(self) -> str:
        try:
            return condition_from_payload(self.alert_type, self.condition).format()
        except (ValidationError, Exception):
            return "Invalid condition"


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
    """Optional filter to scope a manual evaluation. ``None`` runs every type."""

    alert_type: Optional[AlertType] = None
