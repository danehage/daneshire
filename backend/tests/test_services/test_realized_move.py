"""
Unit tests for compute_realized_move (ADR-0003 formula).

No database or network calls — pure function over synthetic bar lists.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.services.market import compute_realized_move


def bars(*entries):
    """Build a bar list from (date_str, close) pairs."""
    return [{"date": d, "close": float(c)} for d, c in entries]


# ---------------------------------------------------------------------------
# Basic cases: bmo / amc / unknown
# ---------------------------------------------------------------------------


def test_bmo_uses_same_day_close():
    """BMO: post_close = close on report_date itself."""
    price_bars = bars(
        ("2026-04-29", 100.0),  # pre_close (day before)
        ("2026-04-30", 108.0),  # report_date → post_close for bmo
        ("2026-05-01", 109.0),
    )
    result = compute_realized_move(price_bars, date(2026, 4, 30), "bmo")
    assert result is not None
    assert abs(float(result) - 0.08) < 1e-9


def test_amc_uses_next_session_close():
    """AMC: post_close = first bar strictly after report_date."""
    price_bars = bars(
        ("2026-04-29", 100.0),  # pre_close
        ("2026-04-30", 102.0),  # report_date close (not used for amc)
        ("2026-05-01", 115.0),  # post_close for amc
    )
    result = compute_realized_move(price_bars, date(2026, 4, 30), "amc")
    assert result is not None
    assert abs(float(result) - 0.15) < 1e-9


def test_unknown_behaves_like_amc():
    """unknown: same as amc — next session after report_date."""
    price_bars = bars(
        ("2026-04-29", 100.0),
        ("2026-04-30", 102.0),
        ("2026-05-01", 90.0),
    )
    result = compute_realized_move(price_bars, date(2026, 4, 30), "unknown")
    assert result is not None
    assert abs(float(result) - 0.10) < 1e-9


def test_move_is_sign_stripped():
    """Realized move is always positive (absolute value) even on a down move."""
    price_bars = bars(
        ("2026-04-29", 100.0),  # pre_close
        ("2026-04-30", 100.0),  # report_date (amc — not used as post)
        ("2026-05-01", 85.0),   # post_close for amc → -15% move, but abs'd
    )
    result = compute_realized_move(price_bars, date(2026, 4, 30), "amc")
    assert result is not None
    assert float(result) >= 0.0
    assert abs(float(result) - 0.15) < 1e-9


# ---------------------------------------------------------------------------
# Holiday-shifted sessions
# ---------------------------------------------------------------------------


def test_bmo_holiday_shifted_uses_next_available_trading_day():
    """BMO: if report_date has no bar (holiday), use the next trading day's close."""
    # report_date = 2026-04-30 (Thursday, hypothetically a market holiday)
    price_bars = bars(
        ("2026-04-29", 100.0),   # pre_close (Wednesday)
        # 2026-04-30 missing — holiday
        ("2026-05-01", 112.0),   # next trading day → post_close for bmo when holiday
    )
    result = compute_realized_move(price_bars, date(2026, 4, 30), "bmo")
    assert result is not None
    assert abs(float(result) - 0.12) < 1e-9


def test_amc_holiday_shifted_skips_to_next_trading_day():
    """AMC: if the day after report_date is a holiday, use the day after that."""
    # report_date = 2026-04-30 (Thursday AMC); Friday 2026-05-01 is a holiday
    price_bars = bars(
        ("2026-04-29", 100.0),   # pre_close
        ("2026-04-30", 101.0),   # report_date (not used for amc)
        # 2026-05-01 missing — holiday
        ("2026-05-04", 95.0),    # next trading day → post_close
    )
    result = compute_realized_move(price_bars, date(2026, 4, 30), "amc")
    assert result is not None
    assert abs(float(result) - 0.05) < 1e-9


# ---------------------------------------------------------------------------
# Insufficient history / null cases
# ---------------------------------------------------------------------------


def test_returns_none_when_no_bars():
    result = compute_realized_move([], date(2026, 4, 30), "bmo")
    assert result is None


def test_returns_none_when_no_pre_close():
    """All bars are on or after report_date — no pre_close available."""
    price_bars = bars(
        ("2026-04-30", 100.0),
        ("2026-05-01", 110.0),
    )
    result = compute_realized_move(price_bars, date(2026, 4, 30), "bmo")
    assert result is None


def test_returns_none_when_no_post_close_amc():
    """AMC with report_date as the last bar — no session after it."""
    price_bars = bars(
        ("2026-04-29", 100.0),
        ("2026-04-30", 102.0),  # report_date = last bar, amc needs day after
    )
    result = compute_realized_move(price_bars, date(2026, 4, 30), "amc")
    assert result is None


def test_returns_none_when_pre_close_is_zero():
    """Avoids division by zero when pre_close is zero."""
    price_bars = bars(
        ("2026-04-29", 0.0),
        ("2026-04-30", 100.0),
    )
    result = compute_realized_move(price_bars, date(2026, 4, 30), "bmo")
    assert result is None


# ---------------------------------------------------------------------------
# Edge: bars out of order
# ---------------------------------------------------------------------------


def test_bars_in_reverse_order():
    """Bars supplied newest-first should still produce the correct result."""
    price_bars = bars(
        ("2026-05-01", 115.0),
        ("2026-04-30", 102.0),
        ("2026-04-29", 100.0),
    )
    result = compute_realized_move(price_bars, date(2026, 4, 30), "amc")
    assert result is not None
    assert abs(float(result) - 0.15) < 1e-9
