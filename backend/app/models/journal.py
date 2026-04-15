from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    Text,
    DateTime,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class JournalEntry(Base):
    __tablename__ = "journal_entries"

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
    ticker: Mapped[Optional[str]] = mapped_column(
        String(10), nullable=True
    )
    title: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True
    )
    entry_type: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="note"
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    # Relationship
    watchlist_item = relationship("WatchlistItem", back_populates="journal_entries")

    __table_args__ = (
        CheckConstraint(
            "entry_type IN ('thesis', 'note', 'entry', 'exit', 'adjustment', 'review')",
            name="valid_entry_type",
        ),
        CheckConstraint(
            "watchlist_id IS NOT NULL OR ticker IS NOT NULL",
            name="journal_requires_ticker_or_watchlist",
        ),
        Index("idx_journal_watchlist", "watchlist_id"),
        Index("idx_journal_type", "entry_type"),
        Index("idx_journal_ticker", "ticker"),
    )
