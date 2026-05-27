"""merge earnings_iv and realized_move_pct heads

Revision ID: 132d09d0267b
Revises: 4f5a6b7c8d9e, f1a2b3c4d5e6
Create Date: 2026-05-27 10:35:55.397141

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '132d09d0267b'
down_revision: Union[str, Sequence[str], None] = ('4f5a6b7c8d9e', 'f1a2b3c4d5e6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
