"""add portfolio snapshot tables

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e5f6
Create Date: 2026-05-21 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b7c8d9e0f1a2'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'accounts',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('account_type', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_accounts_name', 'accounts', ['name'], unique=False)

    op.create_table(
        'portfolio_snapshots',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('account_id', sa.UUID(), nullable=False),
        sa.Column('captured_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('cash_balance', sa.Numeric(precision=14, scale=4), nullable=True),
        sa.Column('total_value', sa.Numeric(precision=14, scale=4), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_snapshots_account_captured', 'portfolio_snapshots', ['account_id', 'captured_at'], unique=False)

    op.create_table(
        'holdings',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('snapshot_id', sa.UUID(), nullable=False),
        sa.Column('watchlist_item_id', sa.UUID(), nullable=True),
        sa.Column('instrument_type', sa.String(length=10), nullable=False),
        sa.Column('ticker', sa.String(length=20), nullable=False),
        sa.Column('qty', sa.Numeric(precision=14, scale=6), nullable=False),
        sa.Column('avg_cost', sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column('market_value_at_snapshot', sa.Numeric(precision=14, scale=4), nullable=True),
        sa.Column('option_type', sa.String(length=10), nullable=True),
        sa.Column('strike', sa.Numeric(precision=14, scale=4), nullable=True),
        sa.Column('expiry', sa.Date(), nullable=True),
        sa.Column('multiplier', sa.Integer(), nullable=True),
        sa.Column('underlying_ticker', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("instrument_type IN ('equity', 'option')", name='valid_instrument_type'),
        sa.ForeignKeyConstraint(['snapshot_id'], ['portfolio_snapshots.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['watchlist_item_id'], ['watchlist_items.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_holdings_snapshot', 'holdings', ['snapshot_id'], unique=False)
    op.create_index('idx_holdings_ticker', 'holdings', ['ticker'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_holdings_ticker', table_name='holdings')
    op.drop_index('idx_holdings_snapshot', table_name='holdings')
    op.drop_table('holdings')
    op.drop_index('idx_snapshots_account_captured', table_name='portfolio_snapshots')
    op.drop_table('portfolio_snapshots')
    op.drop_index('idx_accounts_name', table_name='accounts')
    op.drop_table('accounts')
