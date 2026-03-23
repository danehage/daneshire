from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Index,
    Integer,
    String,
    Date,
    Numeric,
    DateTime,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    ticker: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="watching"
    )
    position_type: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    entry_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 4), nullable=True
    )
    entry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    shares_or_contracts: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cost_basis: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    tags: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(String), nullable=True, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    # Relationships
    price_targets = relationship(
        "PriceTarget", back_populates="watchlist_item", cascade="all, delete-orphan"
    )
    journal_entries = relationship(
        "JournalEntry", back_populates="watchlist_item", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('watching', 'position_open', 'closed')",
            name="valid_status",
        ),
        Index("idx_watchlist_status", "status"),
        Index("idx_watchlist_ticker", "ticker"),
    )
