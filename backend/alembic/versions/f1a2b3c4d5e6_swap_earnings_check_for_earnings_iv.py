"""swap alert_type 'earnings_check' for 'earnings_iv'

Per issue #18 the EarningsCondition stub is replaced by
EarningsExpectedMoveCondition, which uses alert_type 'earnings_iv'.
The old check_type was a stub that never reached production, so
existing rows (if any) are migrated by re-labelling them.

Revision ID: f1a2b3c4d5e6
Revises: e0f1a2b3c4d5
Create Date: 2026-05-26 19:30:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'e0f1a2b3c4d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('valid_alert_type', 'alerts', type_='check')

    # Re-label any stub rows. The old condition payload (eps/operator/value)
    # is incompatible with the new schema, so deactivate them instead of
    # silently leaving broken JSON behind.
    op.execute(
        "UPDATE alerts SET alert_type = 'earnings_iv', status = 'dismissed' "
        "WHERE alert_type = 'earnings_check'"
    )

    op.create_check_constraint(
        'valid_alert_type',
        'alerts',
        "alert_type IN ('price_cross', 'earnings_iv', 'date_reminder', "
        "'technical_signal', 'custom')",
    )


def downgrade() -> None:
    op.drop_constraint('valid_alert_type', 'alerts', type_='check')
    op.execute(
        "UPDATE alerts SET alert_type = 'earnings_check' "
        "WHERE alert_type = 'earnings_iv'"
    )
    op.create_check_constraint(
        'valid_alert_type',
        'alerts',
        "alert_type IN ('price_cross', 'earnings_check', 'date_reminder', "
        "'technical_signal', 'custom')",
    )
