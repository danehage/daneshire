# IV rank lookback cuts over to self-computed at 252 snapshots

> Status: draft — proposed in `daneshire-earnings-iv-prd.md` v0.2. Approve before earnings module build step 1.

`iv_rank` in `iv_snapshots` can come from two sources: tastytrade's provider value (whatever lookback they use, undocumented but believed to be 52-week) or self-computed from our own `iv_snapshots` history. Provider value is available immediately; self-computed becomes possible only after we have enough history. The question is when to cut over and whether mixed sources are acceptable.

## Decision

The cutover is **per ticker, lazy, and one-way**. For each ticker:

- If `iv_snapshots` for that ticker contains < 252 prior daily rows **actually present in the table** (not trading days elapsed), write `iv_rank` from the provider value and set `source = 'tastytrade'`. Missed scheduler runs delay the cutover by the same number of days — accepted as the cost of using rows-on-record as the trigger.
- Once 252 prior rows exist, compute `iv_rank` ourselves: `iv_rank = 100 * (iv30 - min_252d) / (max_252d - min_252d)`, clamped to `[0, 100]`. Set `source = 'self_252d'`.
- A ticker never reverts from `self_252d` to `tastytrade` even if a snapshot is missing for a day. Backfill the gap or live with the noisier number.

The `source` column on `iv_snapshots` records which lookback produced each row. The screener and the `EarningsExpectedMoveCondition` evaluator do **not** care about source — they read `iv_rank` directly. Mixed-source comparisons across tickers are explicitly accepted as a known noise floor during the first year of operation. The success criteria in the PRD (win rate, expectancy) tolerate it; per-bucket edge analysis in v0.3 does not — but v0.3 will not run until enough self-computed history exists across the watchlist.

## Considered options

- **IV-1 — Lazy per-ticker cutover (chosen).** Ships immediately, gets better silently as data accumulates, no migration event, no flag day.
- **IV-2 — Compute both, store both, let consumers pick.** Two columns, two answers, two arguments forever. Rejected.
- **IV-3 — Wait until every watchlist ticker has 252 days before launching the screener.** Year-long delay before the module produces any value. Rejected — the whole point is to start logging trades and accumulating data.
- **IV-4 — Use provider value forever.** Simplest, but loses control over the lookback window when we eventually want it. The bet is that self-computed is worth the consistency once we have the data.

## When to revisit

- If after the first 30 days, more than 20% of snapshots are missing the provider field (tastytrade flake), accelerate the self-computed path by relaxing the 252-day threshold or by backfilling synthetic `iv30` from historical option chains. Don't lower the threshold below 126 days (≈ 6 months) — anything shorter produces a rank that whips on a single high-IV event.
- If the provider value's lookback is documented or discovered to be materially different from 252 trading days, re-evaluate the cutover threshold to match.
