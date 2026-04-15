"""Add title and ticker to journal entries, make watchlist_id nullable

Revision ID: a1b2c3d4e5f6
Revises: d4e3d91957d2
Create Date: 2026-04-14 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'd4e3d91957d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add title column
    op.add_column('journal_entries', sa.Column('title', sa.String(200), nullable=True))

    # Add ticker column for standalone entries
    op.add_column('journal_entries', sa.Column('ticker', sa.String(10), nullable=True))

    # Make watchlist_id nullable
    op.alter_column('journal_entries', 'watchlist_id',
                    existing_type=sa.UUID(),
                    nullable=True)

    # Add constraint: must have either watchlist_id or ticker
    op.create_check_constraint(
        'journal_requires_ticker_or_watchlist',
        'journal_entries',
        'watchlist_id IS NOT NULL OR ticker IS NOT NULL'
    )

    # Add index on ticker for faster lookups
    op.create_index('idx_journal_ticker', 'journal_entries', ['ticker'])


def downgrade() -> None:
    # Remove index
    op.drop_index('idx_journal_ticker', table_name='journal_entries')

    # Remove constraint
    op.drop_constraint('journal_requires_ticker_or_watchlist', 'journal_entries')

    # Make watchlist_id non-nullable (will fail if there are standalone entries)
    op.alter_column('journal_entries', 'watchlist_id',
                    existing_type=sa.UUID(),
                    nullable=False)

    # Remove columns
    op.drop_column('journal_entries', 'ticker')
    op.drop_column('journal_entries', 'title')
