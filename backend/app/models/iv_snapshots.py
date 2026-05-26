from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, DateTime, Index, Numeric, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class IVSnapshot(Base):
    """One daily implied-volatility snapshot per (ticker, date).

    Immutable: rows are written by the daily scheduler and never updated.
    `source` records whether `iv_rank` came from the provider or our
    self-computed 252-row lookback (ADR-0004).
    """

    __tablename__ = "iv_snapshots"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    ticker: Mapped[str] = mapped_column(String(10), nullable=False)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    iv30: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    iv_rank: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    expected_move_pct: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        UniqueConstraint("ticker", "snapshot_date", name="uq_iv_snapshots_ticker_date"),
        CheckConstraint(
            "source IN ('tastytrade', 'self_252d')",
            name="valid_iv_snapshot_source",
        ),
        CheckConstraint(
            "iv_rank >= 0 AND iv_rank <= 100",
            name="iv_rank_bounded",
        ),
        Index("idx_iv_snapshots_ticker_date", "ticker", text("snapshot_date DESC")),
    )
