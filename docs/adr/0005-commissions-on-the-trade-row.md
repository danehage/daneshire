# Commissions live on the earnings trade row

> Status: draft — proposed in `daneshire-earnings-iv-prd.md` v0.2. Approve before earnings module build step 1.

The hypothesis in the earnings PRD is validated only by **net** expectancy — gross P/L on a 4-leg structure can be positive while the net is negative once commissions and assignment fees are in. P/L therefore needs a clear net value, and "where commissions live" must be decided before the schema is written.

## Decision

`earnings_trades` carries a single `commissions` column: `numeric`, default `0`, representing total round-trip fees for the trade (entry legs + exit legs + any assignment fees). PnL is exposed as two SQL-generated columns:

```
pnl_gross = (entry_credit - coalesce(exit_debit, 0)) * contracts * 100
pnl_net   = pnl_gross - commissions
```

- The frontend displays `pnl_net` by default with `pnl_gross` available on hover/expand.
- Per-leg commission breakdown is **not** stored. If a trade has unusual fees (assignment, exercise, regulatory), the total still goes in `commissions` and a free-text note goes in `notes`.
- `commissions` is the single source of truth for fees. The `adjustments` JSONB array is narrative-only and carries `{date, action, notes, premium_delta}` — `premium_delta` is the adjustment's effect on net premium (positive for a credit, negative for a debit). **No commission field lives inside the JSONB.**
- The PATCH handler accepts an optional `commission_delta` argument on adjustment creation and applies it to the `commissions` column in the same transaction. This keeps a single writer and prevents the column from drifting against the JSONB.
- Consequence (acknowledged): per-adjustment fee history is not recoverable. "How much have rolls cost me?" is the v0.3 question this ADR's revisit clause is reserved for.

## Considered options

- **C-1 — Single `commissions` column + generated `pnl_net` (chosen).** Cheapest schema, one source of truth, easy to audit. Trade-off: per-leg analytics impossible without re-parsing notes. Acceptable for v0.1.
- **C-2 — Per-leg commission columns (`entry_commission`, `exit_commission`, `adjustment_commission`).** Enables analytics like "what does rolling actually cost me". Rejected for v0.1 — too much schema for a question we don't have data to answer yet.
- **C-3 — Separate `trade_fees` table, one row per fee event.** Most flexible. Massively over-engineered for a single-user app where the broker statement is the audit of record.
- **C-4 — Don't store commissions; compute from a flat per-contract assumption.** Cheapest, but the whole point is that thin earnings premium gets eaten by fees in ways a flat assumption hides. Defeats the success criterion.

## When to revisit

- If v0.3 analytics needs to answer "is my adjustment behaviour profitable net of fees", promote to **C-2** with a one-shot migration that splits existing `commissions` evenly across entry/exit (acknowledged as lossy).
- If a broker change introduces materially different fee structures per leg type (e.g. zero commission on closing trades), revisit the assumption that one number suffices.
