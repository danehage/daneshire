"""add earnings_events table

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e5f6
Create Date: 2026-05-21 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b7c8d9e0f1a2'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'earnings_events',
        sa.Column(
            'id',
            sa.UUID(),
            server_default=sa.text('gen_random_uuid()'),
            nullable=False,
        ),
        sa.Column('ticker', sa.String(length=10), nullable=False),
        sa.Column('report_date', sa.Date(), nullable=False),
        sa.Column(
            'report_time',
            sa.String(length=10),
            server_default='unknown',
            nullable=False,
        ),
        sa.Column('fiscal_period', sa.String(length=20), nullable=True),
        sa.Column(
            'source',
            sa.String(length=20),
            server_default='finnhub',
            nullable=False,
        ),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.CheckConstraint(
            "report_time IN ('bmo', 'amc', 'unknown')",
            name='valid_report_time',
        ),
        sa.UniqueConstraint('ticker', 'report_date', name='uq_earnings_events_ticker_date'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_earnings_events_ticker', 'earnings_events', ['ticker'], unique=False)
    op.create_index('idx_earnings_events_report_date', 'earnings_events', ['report_date'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_earnings_events_report_date', table_name='earnings_events')
    op.drop_index('idx_earnings_events_ticker', table_name='earnings_events')
    op.drop_table('earnings_events')
