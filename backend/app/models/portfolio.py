from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    account_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    snapshots = relationship(
        "PortfolioSnapshot", back_populates="account", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_accounts_name", "name"),
    )


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    cash_balance: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 4), nullable=True)
    total_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    account = relationship("Account", back_populates="snapshots")
    holdings = relationship(
        "Holding", back_populates="snapshot", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_snapshots_account_captured", "account_id", "captured_at"),
    )


class Holding(Base):
    __tablename__ = "holdings"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("portfolio_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    watchlist_item_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("watchlist_items.id", ondelete="SET NULL"), nullable=True
    )
    instrument_type: Mapped[str] = mapped_column(String(10), nullable=False)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    qty: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    avg_cost: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    market_value_at_snapshot: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(14, 4), nullable=True
    )
    option_type: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    strike: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 4), nullable=True)
    expiry: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    multiplier: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    underlying_ticker: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    snapshot = relationship("PortfolioSnapshot", back_populates="holdings")

    __table_args__ = (
        CheckConstraint(
            "instrument_type IN ('equity', 'option')",
            name="valid_instrument_type",
        ),
        Index("idx_holdings_snapshot", "snapshot_id"),
        Index("idx_holdings_ticker", "ticker"),
    )
