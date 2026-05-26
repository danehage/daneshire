from datetime import date, datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, Index, String, Text, DateTime, text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class EarningsEvent(Base):
    __tablename__ = "earnings_events"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    ticker: Mapped[str] = mapped_column(String(10), nullable=False)
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    report_time: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default="unknown"
    )
    fiscal_period: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, server_default="finnhub")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        UniqueConstraint("ticker", "report_date", name="uq_earnings_events_ticker_date"),
        CheckConstraint(
            "report_time IN ('bmo', 'amc', 'unknown')",
            name="valid_report_time",
        ),
        Index("idx_earnings_events_ticker", "ticker"),
        Index("idx_earnings_events_report_date", "report_date"),
    )
