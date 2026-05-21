# Cloud Scheduler hits internal endpoints, not Cloud Run Jobs

> Status: draft — proposed in `daneshire-earnings-iv-prd.md` v0.2. Reaffirms an established pattern; recorded because the original draft of the earnings PRD proposed deviating.

The alert engine, watchlist reminders, and expiry cleanup are all driven by Cloud Scheduler making authenticated HTTP POSTs to `/api/internal/*` endpoints on the existing Cloud Run service, gated by an `X-Scheduler-Secret` header verified with `secrets.compare_digest()`. The earnings module needs the same kind of recurring work (nightly calendar refresh, daily IV snapshots, earnings-window alert evaluation). The first draft of the earnings PRD proposed Cloud Run Jobs as a separate execution surface. This ADR records why we don't.

## Decision

All recurring earnings-module work goes through `/api/internal/earnings/*` endpoints on the existing FastAPI service, triggered by Cloud Scheduler with the existing `X-Scheduler-Secret` header. No Cloud Run Jobs. No separate worker service. No new authentication scheme.

Specifically:

- `POST /api/internal/earnings/refresh-calendar` — daily 22:00 ET
- `POST /api/internal/earnings/refresh-snapshots` — daily 16:30 ET (after market close)
- `POST /api/internal/alerts/run-earnings-checks` — daily 17:00 ET (after snapshots)
- `POST /api/internal/earnings/backfill-realized-moves` — manual/one-shot, same auth

All four use the existing `verify_scheduler_secret()` dependency from `backend/app/routes/internal.py`. Development bypass (skip auth when `ENVIRONMENT=development` and `SCHEDULER_SECRET` unset) inherits unchanged. Errors return non-2xx so Cloud Scheduler retries per its existing policy.

## Considered options

- **S-1 — Internal endpoints on the same service (chosen).** Same auth, same logging, same deploy pipeline, same observability. Cron config is the only thing that changes per job. Cold-start cost on Cloud Run scales-to-zero is acceptable for daily/nightly cadence.
- **S-2 — Cloud Run Jobs.** Dedicated execution surface, container-based, no HTTP handler. Rejected: introduces a second deploy target with its own image lifecycle, its own IAM, its own logs. The work is not long-running enough to justify it (a calendar refresh is seconds, a snapshot refresh is a minute), and Cloud Run requests time out at 60 minutes — well beyond any earnings batch.
- **S-3 — A dedicated Python worker on a small VM, polling.** Rejected on cost and ops surface — adds an always-on resource for work that runs minutes per day.
- **S-4 — In-process scheduler (APScheduler) inside the same FastAPI app.** Rejected: Cloud Run scales to zero, so an in-process scheduler isn't reliably alive when its trigger fires.

## When to revisit

- Any earnings job grows beyond ~50 minutes of wall-clock work (e.g. realized-move backfill across thousands of tickers). At that point, Cloud Run Jobs becomes appropriate for that one job — the rest stay on internal endpoints. Don't migrate them all together; do it per-job when the constraint actually bites.
- Cloud Scheduler quotas become a problem (currently 30 jobs/region free tier). Far from it today.
