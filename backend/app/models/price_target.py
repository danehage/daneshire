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
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PriceTarget(Base):
    __tablename__ = "price_targets"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    watchlist_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("watchlist_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    label: Mapped[str] = mapped_column(String(50), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    direction: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default="below"
    )
    alert_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    triggered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    # Relationship back to watchlist item
    watchlist_item = relationship("WatchlistItem", back_populates="price_targets")

    __table_args__ = (
        CheckConstraint(
            "direction IN ('above', 'below')",
            name="valid_direction",
        ),
        Index("idx_targets_watchlist", "watchlist_id"),
        Index(
            "idx_targets_active",
            "alert_enabled",
            "triggered_at",
            postgresql_where=text("alert_enabled = true AND triggered_at IS NULL"),
        ),
    )
