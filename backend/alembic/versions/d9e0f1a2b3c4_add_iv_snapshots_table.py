"""add iv_snapshots table

Revision ID: d9e0f1a2b3c4
Revises: c8d9e0f1a2b3
Create Date: 2026-05-26 14:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd9e0f1a2b3c4'
down_revision: Union[str, Sequence[str], None] = 'c8d9e0f1a2b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'iv_snapshots',
        sa.Column(
            'id',
            sa.UUID(),
            server_default=sa.text('gen_random_uuid()'),
            nullable=False,
        ),
        sa.Column('ticker', sa.String(length=10), nullable=False),
        sa.Column('snapshot_date', sa.Date(), nullable=False),
        sa.Column('iv30', sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column('iv_rank', sa.Numeric(precision=6, scale=3), nullable=False),
        sa.Column('expected_move_pct', sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column('source', sa.String(length=20), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source IN ('tastytrade', 'self_252d')",
            name='valid_iv_snapshot_source',
        ),
        sa.CheckConstraint(
            "iv_rank >= 0 AND iv_rank <= 100",
            name='iv_rank_bounded',
        ),
        sa.UniqueConstraint('ticker', 'snapshot_date', name='uq_iv_snapshots_ticker_date'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'idx_iv_snapshots_ticker_date',
        'iv_snapshots',
        ['ticker', sa.text('snapshot_date DESC')],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('idx_iv_snapshots_ticker_date', table_name='iv_snapshots')
    op.drop_table('iv_snapshots')
