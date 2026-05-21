# Defer extracting a market-calendar module

Market-hours logic (9:30–16:00 ET, weekdays) currently lives inside `calculate_volume_pace` in `backend/app/services/indicators.py`. A 2026-05 architecture review flagged this as buried domain knowledge and proposed extracting a `market_calendar` module exposing `is_session_open(now)` and `minutes_into_session(now)`. We considered three paths and chose to defer.

## Decision

Leave market-hours logic where it is. Revisit when a second concrete caller exists.

## Considered options

- **MC-1 — Extract now, minimal.** `market_calendar.py` with `is_session_open` and `minutes_into_session`. `calculate_volume_pace` consumes it; alert engine adds a defensive guard against out-of-hours manual `/api/alerts/evaluate` calls. Rejected: the alert-engine guard is purely defensive (Cloud Scheduler already enforces hours via cron), so the "second caller" is hypothetical — one real adapter behind the seam.
- **MC-2 — Extract now, with a market-status API endpoint.** Adds `GET /api/market/status` for a dashboard banner. Three real consumers (volume pace + alert engine guard + frontend dashboard). Rejected: we don't actually want the dashboard banner right now; building the endpoint just to justify the seam is backward.
- **MC-3 — Defer (chosen).** Record the decision so future architecture reviews don't re-suggest the same extraction.

## When to revisit

Any of these makes the extraction earn its keep:

- The dashboard gains a "market open / closed in X" indicator that needs backend support.
- Volume-pace correctness starts mattering on half-days or holidays — needs holiday-aware calendar logic that wouldn't be tolerable buried inside one indicator function.
- A third independent caller of session-time logic appears (cache invalidation across open/close boundaries, an "only run scans during market hours" guard, etc.).

Until then, the rule from `LANGUAGE.md` applies: one adapter is a hypothetical seam. Don't introduce the seam until something actually varies behind it.
