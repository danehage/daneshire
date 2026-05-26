"""add earnings_trades table

Revision ID: e0f1a2b3c4d5
Revises: d9e0f1a2b3c4
Create Date: 2026-05-26 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e0f1a2b3c4d5'
down_revision: Union[str, Sequence[str], None] = 'd9e0f1a2b3c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'earnings_trades',
        sa.Column(
            'id',
            sa.UUID(),
            server_default=sa.text('gen_random_uuid()'),
            nullable=False,
        ),
        sa.Column('ticker', sa.String(length=10), nullable=False),
        sa.Column('watchlist_item_id', sa.UUID(), nullable=True),
        sa.Column('earnings_event_id', sa.UUID(), nullable=False),
        sa.Column('structure', sa.String(length=20), nullable=False),
        sa.Column('is_paper', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('entry_date', sa.Date(), nullable=False),
        sa.Column('expiry_date', sa.Date(), nullable=False),
        sa.Column('exit_date', sa.Date(), nullable=True),
        sa.Column('short_put_strike', sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column('long_put_strike', sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column('short_call_strike', sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column('long_call_strike', sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column('entry_credit', sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column('exit_debit', sa.Numeric(precision=14, scale=4), nullable=True),
        sa.Column('contracts', sa.Integer(), nullable=False),
        sa.Column('commissions', sa.Numeric(precision=14, scale=4), nullable=False, server_default=sa.text('0')),
        sa.Column('entry_iv_rank', sa.Numeric(precision=6, scale=3), nullable=True),
        sa.Column('entry_expected_move_pct', sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column('realized_move_pct', sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column(
            'pnl_gross',
            sa.Numeric(precision=16, scale=4),
            sa.Computed(
                '(entry_credit - COALESCE(exit_debit, 0)) * contracts * 100',
                persisted=True,
            ),
            nullable=True,
        ),
        sa.Column(
            'pnl_net',
            sa.Numeric(precision=16, scale=4),
            sa.Computed(
                '((entry_credit - COALESCE(exit_debit, 0)) * contracts * 100) - commissions',
                persisted=True,
            ),
            nullable=True,
        ),
        sa.Column(
            'adjustments',
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='open'),
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
        sa.ForeignKeyConstraint(
            ['watchlist_item_id'], ['watchlist_items.id'], ondelete='SET NULL'
        ),
        sa.ForeignKeyConstraint(
            ['earnings_event_id'], ['earnings_events.id'], ondelete='RESTRICT'
        ),
        sa.CheckConstraint(
            "structure IN ('iron_condor', 'iron_butterfly')",
            name='valid_structure',
        ),
        sa.CheckConstraint(
            "status IN ('open', 'closed', 'expired', 'assigned')",
            name='valid_trade_status',
        ),
        sa.CheckConstraint(
            "long_put_strike <= short_put_strike "
            "AND short_put_strike <= short_call_strike "
            "AND short_call_strike <= long_call_strike",
            name='valid_strike_ordering',
        ),
        sa.CheckConstraint('contracts > 0', name='positive_contracts'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_earnings_trades_ticker', 'earnings_trades', ['ticker'])
    op.create_index('idx_earnings_trades_status', 'earnings_trades', ['status'])
    op.create_index('idx_earnings_trades_entry_date', 'earnings_trades', ['entry_date'])
    op.create_index(
        'idx_earnings_trades_earnings_event_id',
        'earnings_trades',
        ['earnings_event_id'],
    )


def downgrade() -> None:
    op.drop_index('idx_earnings_trades_earnings_event_id', table_name='earnings_trades')
    op.drop_index('idx_earnings_trades_entry_date', table_name='earnings_trades')
    op.drop_index('idx_earnings_trades_status', table_name='earnings_trades')
    op.drop_index('idx_earnings_trades_ticker', table_name='earnings_trades')
    op.drop_table('earnings_trades')
