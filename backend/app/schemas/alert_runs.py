"""
Result schemas for ``AlertEngine.run`` / ``run_all``.

Returned by the four internal cron endpoints and the manual
``POST /api/alerts/evaluate``. Per-alert outcomes are included so the
manual endpoint can be used as a debugging surface.
"""

from __future__ import annotations

from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


OutcomeStatus = Literal["met", "not_met", "errored"]


class AlertOutcomeRecord(BaseModel):
    """One alert × one evaluation, flattened for transport.

    Mirrors :class:`app.schemas.alert_conditions.Outcome` but as a single
    Pydantic shape so the API consumer doesn't have to discriminate.
    """

    model_config = ConfigDict(frozen=True)

    alert_id: UUID
    ticker: str
    status: OutcomeStatus
    actual_value: Optional[float] = None
    reason: Optional[str] = None


class RunSummary(BaseModel):
    """Aggregate result of ``AlertEngine.run``.

    ``alert_type`` echoes the input filter; ``run_all`` sets it to
    ``"all"``. Counts always sum to ``len(outcomes)``.
    """

    model_config = ConfigDict(frozen=True)

    alert_type: str
    met: int = 0
    not_met: int = 0
    errored: int = 0
    notifications_sent: int = 0
    outcomes: list[AlertOutcomeRecord] = []

    def merged_with(self, other: "RunSummary") -> "RunSummary":
        return RunSummary(
            alert_type=self.alert_type if self.alert_type == other.alert_type else "all",
            met=self.met + other.met,
            not_met=self.not_met + other.not_met,
            errored=self.errored + other.errored,
            notifications_sent=self.notifications_sent + other.notifications_sent,
            outcomes=[*self.outcomes, *other.outcomes],
        )
