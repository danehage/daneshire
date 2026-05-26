from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class EarningsTrade(Base):
    """One row per earnings trade.

    Per ADR-0005, `commissions` is the single source of truth for fees;
    `pnl_gross` and `pnl_net` are Postgres GENERATED columns derived
    from `entry_credit`, `exit_debit`, `contracts`, and `commissions`.
    `adjustments` is narrative-only JSONB — no fee data lives inside.
    """

    __tablename__ = "earnings_trades"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    ticker: Mapped[str] = mapped_column(String(10), nullable=False)
    watchlist_item_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("watchlist_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    earnings_event_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("earnings_events.id", ondelete="RESTRICT"),
        nullable=False,
    )
    structure: Mapped[str] = mapped_column(String(20), nullable=False)
    is_paper: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )

    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False)
    exit_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    short_put_strike: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    long_put_strike: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    short_call_strike: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    long_call_strike: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)

    entry_credit: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    exit_debit: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 4), nullable=True)
    contracts: Mapped[int] = mapped_column(Integer, nullable=False)
    commissions: Mapped[Decimal] = mapped_column(
        Numeric(14, 4), nullable=False, server_default=text("0")
    )

    entry_iv_rank: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 3), nullable=True)
    entry_expected_move_pct: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 6), nullable=True
    )
    realized_move_pct: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 6), nullable=True
    )

    pnl_gross: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(16, 4),
        Computed(
            "(entry_credit - COALESCE(exit_debit, 0)) * contracts * 100",
            persisted=True,
        ),
        nullable=True,
    )
    pnl_net: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(16, 4),
        Computed(
            "((entry_credit - COALESCE(exit_debit, 0)) * contracts * 100) - commissions",
            persisted=True,
        ),
        nullable=True,
    )

    adjustments: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="open"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint(
            "structure IN ('iron_condor', 'iron_butterfly')", name="valid_structure"
        ),
        CheckConstraint(
            "status IN ('open', 'closed', 'expired', 'assigned')",
            name="valid_trade_status",
        ),
        CheckConstraint(
            "long_put_strike <= short_put_strike "
            "AND short_put_strike <= short_call_strike "
            "AND short_call_strike <= long_call_strike",
            name="valid_strike_ordering",
        ),
        CheckConstraint("contracts > 0", name="positive_contracts"),
        Index("idx_earnings_trades_ticker", "ticker"),
        Index("idx_earnings_trades_status", "status"),
        Index("idx_earnings_trades_entry_date", "entry_date"),
        Index("idx_earnings_trades_earnings_event_id", "earnings_event_id"),
    )
