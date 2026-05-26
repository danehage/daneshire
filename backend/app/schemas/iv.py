"""Schemas for implied-volatility snapshots.

`IVSnapshotRaw` is the wire-level dataclass returned by
:class:`TastytradeClient.get_iv_snapshot` and surfaced by the
`MarketData.iv_snapshot(s)` seam methods. It holds the provider-derived
fields; the seam's caller (the internal refresh endpoint) decides how to
persist them — including which IV-rank source to use (ADR-0004) — and
maps to the `IVSnapshot` ORM row.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass(frozen=True)
class IVSnapshotRaw:
    """Provider-derived IV snapshot for one ticker on one day.

    `expected_move_pct` is ``None`` when the front-week ATM straddle
    could not be priced (zero bid+ask and no usable last); per ADR-0003
    such snapshots must not be written.
    """

    ticker: str
    iv30: Decimal
    iv_rank_provider: Decimal
    expected_move_pct: Optional[Decimal]
