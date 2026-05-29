"""add trades table

Revision ID: a2b3c4d5e6f7
Revises: 132d09d0267b
Create Date: 2026-05-27 14:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a2b3c4d5e6f7'
down_revision: Union[str, None] = '132d09d0267b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'trades',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('account_id', sa.UUID(), nullable=False),
        sa.Column('watchlist_item_id', sa.UUID(), nullable=True),
        sa.Column('ticker', sa.String(length=20), nullable=False),
        sa.Column('instrument_type', sa.String(length=10), nullable=False),
        sa.Column('side', sa.String(length=4), nullable=False),
        sa.Column('qty', sa.Numeric(precision=14, scale=6), nullable=False),
        sa.Column('price', sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column('option_type', sa.String(length=10), nullable=True),
        sa.Column('strike', sa.Numeric(precision=14, scale=4), nullable=True),
        sa.Column('expiry', sa.Date(), nullable=True),
        sa.Column('multiplier', sa.Integer(), nullable=True),
        sa.Column('underlying_ticker', sa.String(length=20), nullable=True),
        sa.Column('realized_pl', sa.Numeric(precision=14, scale=4), nullable=True),
        sa.Column('executed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("instrument_type IN ('equity', 'option')", name='valid_trade_instrument_type'),
        sa.CheckConstraint("side IN ('buy', 'sell')", name='valid_trade_side'),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['watchlist_item_id'], ['watchlist_items.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_trades_account_executed', 'trades', ['account_id', 'executed_at'], unique=False)
    op.create_index('idx_trades_ticker', 'trades', ['ticker'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_trades_ticker', table_name='trades')
    op.drop_index('idx_trades_account_executed', table_name='trades')
    op.drop_table('trades')
