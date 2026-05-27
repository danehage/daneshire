"""add realized_move_pct to earnings_events

Revision ID: 4f5a6b7c8d9e
Revises: e0f1a2b3c4d5
Create Date: 2026-05-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4f5a6b7c8d9e'
down_revision: Union[str, Sequence[str], None] = 'e0f1a2b3c4d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'earnings_events',
        sa.Column('realized_move_pct', sa.Numeric(precision=10, scale=6), nullable=True),
    )
    op.create_index(
        'idx_earnings_events_realized_move',
        'earnings_events',
        ['ticker', 'realized_move_pct'],
        postgresql_where=sa.text('realized_move_pct IS NOT NULL'),
    )


def downgrade() -> None:
    op.drop_index('idx_earnings_events_realized_move', table_name='earnings_events')
    op.drop_column('earnings_events', 'realized_move_pct')
