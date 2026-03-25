from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    DateTime,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    watchlist_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("watchlist_items.id", ondelete="CASCADE"),
        nullable=True,
    )
    ticker: Mapped[str] = mapped_column(String(10), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    alert_type: Mapped[str] = mapped_column(String(30), nullable=False)
    condition: Mapped[dict] = mapped_column(JSONB, nullable=False)
    action_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="active"
    )
    priority: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default="normal"
    )
    triggered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    # Relationships
    watchlist_item = relationship("WatchlistItem", backref="alerts")
    history = relationship(
        "AlertHistory", back_populates="alert", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "alert_type IN ('price_cross', 'earnings_check', 'date_reminder', "
            "'technical_signal', 'custom')",
            name="valid_alert_type",
        ),
        CheckConstraint(
            "status IN ('active', 'triggered', 'dismissed', 'expired')",
            name="valid_alert_status",
        ),
        CheckConstraint(
            "priority IN ('low', 'normal', 'high', 'urgent')",
            name="valid_alert_priority",
        ),
        Index("idx_alerts_active", "status", postgresql_where=text("status = 'active'")),
        Index("idx_alerts_ticker", "ticker"),
        Index("idx_alerts_type", "alert_type"),
    )


class AlertHistory(Base):
    __tablename__ = "alert_history"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    alert_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("alerts.id", ondelete="CASCADE"),
        nullable=False,
    )
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    condition_met: Mapped[bool] = mapped_column(Boolean, nullable=False)
    actual_value: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 4), nullable=True
    )
    notification_sent: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    alert = relationship("Alert", back_populates="history")

    __table_args__ = (
        Index("idx_alert_history_alert", "alert_id"),
        Index(
            "idx_alert_history_triggered",
            "condition_met",
            postgresql_where=text("condition_met = true"),
        ),
    )
