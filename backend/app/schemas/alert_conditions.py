"""
Typed alert conditions — the discriminated union behind the JSONB
``alerts.condition`` column.

Each variant owns:

* Pydantic validation (operator allow-list, value coercion)
* ``.evaluate(observation)`` — pure, deterministic, no I/O
* ``.format()`` — single-source human string for UI and notifications

The orchestrator in ``app.services.alert_engine`` constructs variants
from stored ``Alert`` rows via :func:`condition_from_alert`, dispatching
on ``alert.alert_type``. Adding a new operator or metric stays inside
this file.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from operator import eq, ge, gt, le, lt
from typing import Any, Callable, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.market import PriceQuote, TechnicalAnalysis


# ---------------------------------------------------------------------------
# Outcomes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Met:
    """Condition was satisfied. ``actual_value`` is the observation read."""

    actual_value: Optional[float] = None


@dataclass(frozen=True)
class NotMet:
    """Condition was evaluated against a valid observation and was false."""

    actual_value: Optional[float] = None


@dataclass(frozen=True)
class Errored:
    """Condition could not be evaluated (missing obs, fetch failure, etc.).

    Constructed only by the orchestrator — the pure evaluator's return
    type is narrowed to :class:`Met` | :class:`NotMet`.
    """

    reason: str


EvalResult = Union[Met, NotMet]
Outcome = Union[Met, NotMet, Errored]


# ---------------------------------------------------------------------------
# Operator vocabulary — single source of truth
# ---------------------------------------------------------------------------


Operator = Literal[">", ">=", "<", "<=", "=="]

_OP_FUNCS: dict[Operator, Callable[[float, float], bool]] = {
    ">": gt,
    ">=": ge,
    "<": lt,
    "<=": le,
    "==": eq,
}


def _compare(operator: Operator, actual: float, target: float) -> bool:
    return _OP_FUNCS[operator](actual, target)


# ---------------------------------------------------------------------------
# Condition variants
# ---------------------------------------------------------------------------


class _ConditionBase(BaseModel):
    """Shared config for all condition variants."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class PriceCondition(_ConditionBase):
    """``price`` crossing a threshold. Observation: ``PriceQuote``.

    Accepts ``TechnicalAnalysis`` as well — the analysis payload includes
    ``price``, so the orchestrator can re-use a richer observation when
    technical and price checks fan out together.
    """

    metric: Literal["price"] = "price"
    operator: Operator
    value: float

    def evaluate(
        self, observation: Union[PriceQuote, TechnicalAnalysis]
    ) -> EvalResult:
        actual = float(observation.price)
        if _compare(self.operator, actual, self.value):
            return Met(actual_value=actual)
        return NotMet(actual_value=actual)

    def format(self) -> str:
        return f"price {self.operator} ${self.value:.2f}"


# Metrics that come from ``TechnicalAnalysis`` and are float-comparable.
TechnicalMetric = Literal[
    "rsi",
    "hv_rank",
    "current_hv",
    "range_position",
    "momentum_10d",
    "volume_ratio",
    "volume_pace",
    "dist_50",
    "dist_200",
    "ma_slope",
    "change",
    "change_pct",
    "volume",
]


class TechnicalCondition(_ConditionBase):
    """RSI / HV rank / momentum / etc. Observation: ``TechnicalAnalysis``."""

    metric: TechnicalMetric
    operator: Operator
    value: float

    def evaluate(self, observation: TechnicalAnalysis) -> EvalResult:
        actual = getattr(observation, self.metric, None)
        if actual is None:
            # Defensive: an analysis missing a documented field shouldn't
            # silently match. Treat as "not met" with no recorded value —
            # the orchestrator can decide to surface this distinctly if
            # we later want to.
            return NotMet(actual_value=None)
        actual_f = float(actual)
        if _compare(self.operator, actual_f, self.value):
            return Met(actual_value=actual_f)
        return NotMet(actual_value=actual_f)

    def format(self) -> str:
        return f"{self.metric} {self.operator} {_format_metric_value(self.metric, self.value)}"


@dataclass(frozen=True)
class EarningsIVObservation:
    """Pure observation for ``EarningsExpectedMoveCondition``.

    The orchestrator populates both fields from the database — no
    external I/O. ``None`` on either side means we lack the data
    needed to evaluate (no snapshot for the ticker, or no upcoming
    earnings event), and the pure evaluator surfaces that as
    ``NotMet`` with no recorded value.
    """

    iv_rank: Optional[float]
    days_until_earnings: Optional[int]


class EarningsExpectedMoveCondition(_ConditionBase):
    """Fire when an earnings event is approaching AND IV-rank crosses a threshold.

    Concretely: "alert me ``days_before`` days before earnings if
    ``iv_rank operator value``". The window is inclusive — exactly
    ``days_before`` days out fires; the day of earnings (0 days) also
    fires. Past earnings (negative days) never fire.
    """

    metric: Literal["earnings_iv"] = "earnings_iv"
    operator: Operator = ">="
    value: float = Field(..., ge=0, le=100, description="IV-rank threshold (0–100)")
    days_before: int = Field(..., ge=0, le=60)

    def evaluate(self, observation: EarningsIVObservation) -> EvalResult:
        if observation.days_until_earnings is None or observation.iv_rank is None:
            return NotMet(actual_value=None)
        if observation.days_until_earnings < 0:
            return NotMet(actual_value=observation.iv_rank)
        if observation.days_until_earnings > self.days_before:
            return NotMet(actual_value=observation.iv_rank)
        if _compare(self.operator, observation.iv_rank, self.value):
            return Met(actual_value=observation.iv_rank)
        return NotMet(actual_value=observation.iv_rank)

    def format(self) -> str:
        return (
            f"iv_rank {self.operator} {self.value:.1f} "
            f"within {self.days_before}d of earnings"
        )


class ReminderCondition(_ConditionBase):
    """Date-only reminder. Observation is ``None``; the orchestrator
    decides "is today the trigger day?" and only invokes ``.evaluate``
    when the answer is yes."""

    metric: Literal["reminder"] = "reminder"
    trigger_date: str = Field(..., description="ISO date for the reminder")

    def evaluate(self, observation: None = None) -> EvalResult:
        # When the orchestrator invokes evaluate on a reminder, the
        # gating logic (today == trigger_date) has already passed.
        return Met(actual_value=None)

    def format(self) -> str:
        return f"reminder on {self.trigger_date}"

    @property
    def trigger_date_parsed(self) -> Optional[date]:
        try:
            return datetime.fromisoformat(self.trigger_date).date()
        except (TypeError, ValueError):
            return None


class CustomCondition(_ConditionBase):
    """Reserved slot for user-defined conditions. Always errors today."""

    metric: Literal["custom"] = "custom"
    payload: dict[str, Any] = Field(default_factory=dict)

    def evaluate(self, observation: Any) -> EvalResult:
        # Never called — orchestrator short-circuits to Errored. The
        # method exists so the variant satisfies the same shape.
        return NotMet(actual_value=None)

    def format(self) -> str:
        return "custom condition"


Condition = Union[
    PriceCondition,
    TechnicalCondition,
    EarningsExpectedMoveCondition,
    ReminderCondition,
    CustomCondition,
]


# ---------------------------------------------------------------------------
# Factory — alert_type drives which variant we parse
# ---------------------------------------------------------------------------


# Single mapping from the row's ``alert_type`` to the concrete Condition
# class. The orchestrator's ``match`` and this dispatch are deliberately
# the only two places that enumerate alert types.
_CONDITION_BY_ALERT_TYPE: dict[str, type[Condition]] = {
    "price_cross": PriceCondition,
    "technical_signal": TechnicalCondition,
    "earnings_iv": EarningsExpectedMoveCondition,
    "date_reminder": ReminderCondition,
    "custom": CustomCondition,
}


def condition_from_payload(alert_type: str, payload: dict[str, Any]) -> Condition:
    """Parse a raw condition dict into the variant matching ``alert_type``.

    Raises ``pydantic.ValidationError`` on bad input. ``KeyError`` if
    ``alert_type`` is unknown (caller has typically already validated
    this against the model check constraint).
    """
    cls = _CONDITION_BY_ALERT_TYPE[alert_type]
    return cls.model_validate(payload)


def condition_from_alert(alert: Any) -> Condition:
    """Convenience for parsing the condition off an ``Alert`` ORM row."""
    return condition_from_payload(alert.alert_type, dict(alert.condition))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _format_metric_value(metric: str, value: float) -> str:
    if metric in ("rsi", "hv_rank", "current_hv", "range_position"):
        return f"{value:.1f}"
    if metric in ("change_pct", "momentum_10d"):
        return f"{value:.2f}%"
    if metric == "volume":
        return f"{int(value):,}"
    return f"{value:.2f}"
