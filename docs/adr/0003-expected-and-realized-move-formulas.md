# Expected-move and realized-move formulas

> Status: draft — proposed in `daneshire-earnings-iv-prd.md` v0.2. Approve before earnings module build step 1.

The earnings screener ranks events by `edge_ratio = expected_move_pct / historical_avg_realized_move_pct`. Both numerator and denominator have multiple defensible definitions. Picking now prevents two sessions from implementing two different definitions and silently producing different rankings.

## Decision

**Expected move** is the front-week straddle approximation:

```
expected_move_pct = (atm_call_mid + atm_put_mid) / underlying_price
```

- "ATM" = the strike closest to `underlying_price`. Tie-break: lower strike.
- "Front week" = the nearest weekly expiry that falls strictly after `report_date`. For Friday earnings, this is typically the same-week Friday; for after-hours Thursday earnings, also the same-week Friday. If the expected weekly is shifted by a market holiday (e.g. Good Friday → Thursday expiry), use whatever expiry tastytrade publishes for that week — we do not second-guess the chain.
- "Mid" = `(bid + ask) / 2`. If either side is zero, fall back to `last`. If that is also zero or stale (>10 min), the snapshot is rejected and `iv_snapshots` is not written for that ticker that day.

**Realized move** is sign-stripped, anchored to the last regular session close before the announcement:

```
realized_move_pct = abs((post_close - pre_close) / pre_close)
```

- `pre_close` = the last regular session close strictly before `report_date` (or before the bmo bell on `report_date`).
- `post_close` depends on `report_time`:
  - `bmo` → same-day close on `report_date`
  - `amc` → next regular session close after `report_date`
  - `unknown` → next regular session close after `report_date` (treat as amc; conservative — moves more time on the clock for the move to play out)
- We compare close-to-close, not open-to-close. After-hours gaps are part of the move we are short.

**Historical baseline** is the simple average of the last 8 quarters of realized moves for the same ticker. If fewer than 8 quarters are available (recent IPO, ticker change), use what exists with a minimum of 4. Below 4, the ticker is excluded from the screener — no edge ratio can be computed responsibly.

## Considered options

- **EM-1 — Front-week straddle (chosen for expected move).** Industry-standard approximation, matches tastytrade's "expected move" field within rounding, easy to recompute from raw chain data if the provider's value is missing.
- **EM-2 — Iron-fly width as expected move.** More aligned with the structures we trade, but circular — we'd be measuring the structure against itself.
- **EM-3 — Implied vol × √(days_to_expiry/365).** Theoretically cleanest. Rejected: requires picking which IV (30-day? front-month?) and the answer is materially different for high-IV-rank names where the term structure is steep.
- **RM-1 — Close-to-close, sign-stripped (chosen for realized move).** Symmetric to expected move (also a magnitude), captures the full overnight gap.
- **RM-2 — Open-to-close on the post-earnings session.** Misses the gap, which is most of the move for amc reports. Wrong.
- **RM-3 — Largest intraday absolute return in the next 1–2 sessions.** Closer to what a same-week short condor actually risks, but too sensitive to single-print outliers. Defer until v0.3 analytics has the data to compare.

## When to revisit

- Once `earnings_trades` has ≥ 50 rows, run the v0.3 calibration view: is expected move a good predictor of *my* realized P/L? If RM-1 systematically under-states what hits the position (e.g. iron condors getting tested intraday but resolving by close), promote RM-3 to the canonical realized-move definition.
- If tastytrade's "expected move" field drifts from EM-1 by >5% on average, switch the snapshot to use the provider field verbatim and demote the computed value to a sanity check.
