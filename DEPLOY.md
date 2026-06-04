# Deployment Guide — Danecast Trades

## Prerequisites

- GCP project with billing enabled
- `gcloud` CLI installed and authenticated
- Cloud Run, Cloud Build, Cloud Scheduler APIs enabled

```bash
gcloud services enable run.googleapis.com cloudbuild.googleapis.com cloudscheduler.googleapis.com
```

---

## 1. Set Up Secrets

Store sensitive values in Secret Manager (recommended) or as environment variables.

```bash
# Create secrets
gcloud secrets create neon-database-url --replication-policy="automatic"
echo -n "postgresql+asyncpg://user:pass@host/db?ssl=require" | \
  gcloud secrets versions add neon-database-url --data-file=-

gcloud secrets create fmp-api-key --replication-policy="automatic"
echo -n "your-fmp-api-key" | \
  gcloud secrets versions add fmp-api-key --data-file=-

gcloud secrets create pushover-user-key --replication-policy="automatic"
echo -n "your-pushover-user-key" | \
  gcloud secrets versions add pushover-user-key --data-file=-

gcloud secrets create pushover-api-token --replication-policy="automatic"
echo -n "your-pushover-app-token" | \
  gcloud secrets versions add pushover-api-token --data-file=-

gcloud secrets create scheduler-secret --replication-policy="automatic"
echo -n "$(openssl rand -hex 32)" | \
  gcloud secrets versions add scheduler-secret --data-file=-

# Basic auth credentials (protects web access)
gcloud secrets create auth-username --replication-policy="automatic"
echo -n "your-chosen-username" | \
  gcloud secrets versions add auth-username --data-file=-

gcloud secrets create auth-password --replication-policy="automatic"
echo -n "your-secure-password" | \
  gcloud secrets versions add auth-password --data-file=-

# Earnings module (Finnhub calendar)
gcloud secrets create finnhub-api-key --replication-policy="automatic"
echo -n "your-finnhub-api-key" | \
  gcloud secrets versions add finnhub-api-key --data-file=-

# Tastytrade OAuth2 (server-to-server refresh-token grant)
# Obtain client_secret and refresh_token via the Create Grant flow in your
# Tastytrade developer dashboard. See PR #34 / commit 5a3c97e for migration notes.
gcloud secrets create tastytrade-client-secret --replication-policy="automatic"
echo -n "your-tastytrade-client-secret" | \
  gcloud secrets versions add tastytrade-client-secret --data-file=-

gcloud secrets create tastytrade-refresh-token --replication-policy="automatic"
echo -n "your-tastytrade-refresh-token" | \
  gcloud secrets versions add tastytrade-refresh-token --data-file=-
```

---

## 2. Deploy to Cloud Run

### Option A: Manual Deploy

```bash
# Build and push image
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/danecast-trades

# Deploy with secrets
gcloud run deploy danecast-trades \
  --image gcr.io/YOUR_PROJECT_ID/danecast-trades \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars "ENVIRONMENT=production" \
  --set-secrets "NEON_DATABASE_URL=neon-database-url:latest" \
  --set-secrets "FMP_API_KEY=fmp-api-key:latest" \
  --set-secrets "PUSHOVER_USER_KEY=pushover-user-key:latest" \
  --set-secrets "PUSHOVER_API_TOKEN=pushover-api-token:latest" \
  --set-secrets "SCHEDULER_SECRET=scheduler-secret:latest" \
  --set-secrets "AUTH_USERNAME=auth-username:latest" \
  --set-secrets "AUTH_PASSWORD=auth-password:latest" \
  --set-secrets "FINNHUB_API_KEY=finnhub-api-key:latest" \
  --set-secrets "TASTYTRADE_CLIENT_SECRET=tastytrade-client-secret:latest" \
  --set-secrets "TASTYTRADE_REFRESH_TOKEN=tastytrade-refresh-token:latest" \
  --min-instances 0 \
  --max-instances 1 \
  --memory 512Mi \
  --cpu 1

# Note: --allow-unauthenticated is still needed for the app to be reachable.
# The app itself enforces Basic HTTP Auth for all routes except health checks.
```

### Option B: Cloud Build (CI/CD)

Connect your GitHub repo to Cloud Build, then pushes to `main` will auto-deploy.

```bash
# Trigger a build manually
gcloud builds submit --config cloudbuild.yaml
```

Note: For Cloud Build deploys, add secrets to the deploy step in `cloudbuild.yaml`:
```yaml
- '--set-secrets'
- 'NEON_DATABASE_URL=neon-database-url:latest,FMP_API_KEY=fmp-api-key:latest,...'
```

---

## 3. Run Database Migrations

After first deploy, run Alembic migrations:

```bash
# Connect to Cloud Run instance (or run locally with prod DATABASE_URL)
gcloud run jobs create migrate-db \
  --image gcr.io/YOUR_PROJECT_ID/danecast-trades \
  --region us-central1 \
  --set-secrets "NEON_DATABASE_URL=neon-database-url:latest" \
  --command "alembic" \
  --args "upgrade,head"

gcloud run jobs execute migrate-db --region us-central1
```

Or run locally:
```bash
cd backend
NEON_DATABASE_URL="your-prod-url" alembic upgrade head
```

---

## 4. Set Up Cloud Scheduler (Alert Engine)

Get your Cloud Run service URL:
```bash
SERVICE_URL=$(gcloud run services describe danecast-trades --region us-central1 --format 'value(status.url)')
```

Get the scheduler secret:
```bash
SCHEDULER_SECRET=$(gcloud secrets versions access latest --secret=scheduler-secret)
```

### Price Checks (every 15 min, market hours)

```bash
gcloud scheduler jobs create http alert-price-checks \
  --location us-central1 \
  --schedule "*/15 9-16 * * 1-5" \
  --time-zone "America/New_York" \
  --uri "${SERVICE_URL}/api/internal/alerts/run-price-checks" \
  --http-method POST \
  --headers "X-Scheduler-Secret=${SCHEDULER_SECRET}" \
  --attempt-deadline 60s
```

### Technical Checks (every 15 min, market hours)

```bash
gcloud scheduler jobs create http alert-technical-checks \
  --location us-central1 \
  --schedule "*/15 9-16 * * 1-5" \
  --time-zone "America/New_York" \
  --uri "${SERVICE_URL}/api/internal/alerts/run-technical-checks" \
  --http-method POST \
  --headers "X-Scheduler-Secret=${SCHEDULER_SECRET}" \
  --attempt-deadline 60s
```

### Daily Reminders (8 AM ET)

```bash
gcloud scheduler jobs create http alert-reminders \
  --location us-central1 \
  --schedule "0 8 * * *" \
  --time-zone "America/New_York" \
  --uri "${SERVICE_URL}/api/internal/alerts/run-reminders" \
  --http-method POST \
  --headers "X-Scheduler-Secret=${SCHEDULER_SECRET}" \
  --attempt-deadline 60s
```

### Expire Stale Alerts (midnight ET)

```bash
gcloud scheduler jobs create http alert-expire-stale \
  --location us-central1 \
  --schedule "0 0 * * *" \
  --time-zone "America/New_York" \
  --uri "${SERVICE_URL}/api/internal/alerts/expire-stale" \
  --http-method POST \
  --headers "X-Scheduler-Secret=${SCHEDULER_SECRET}" \
  --attempt-deadline 60s
```

---

## 4b. Cloud Scheduler — Earnings Module

Three additional jobs drive the earnings module: the calendar refresh,
the daily IV snapshot, and the per-event alert check. They share the
same `X-Scheduler-Secret` header pattern as the alert-engine jobs above.

Prerequisites: `FINNHUB_API_KEY`, `TASTYTRADE_CLIENT_SECRET`, and
`TASTYTRADE_REFRESH_TOKEN` must be provisioned in Secret Manager and
bound to the Cloud Run service before the snapshot job will succeed (see
env-vars table below). Mint the Tastytrade refresh token via Manage →
API → OAuth Applications → Create Grant.

### Earnings calendar refresh (daily 10 PM ET)

Pulls the next ~4 weeks of upcoming earnings events from Finnhub and
upserts into `earnings_events`. Runs after US market close to capture
any late additions for the next session.

```bash
gcloud scheduler jobs create http earnings-refresh-calendar \
  --location us-central1 \
  --schedule "0 22 * * *" \
  --time-zone "America/New_York" \
  --uri "${SERVICE_URL}/api/internal/earnings/refresh-calendar" \
  --http-method POST \
  --headers "X-Scheduler-Secret=${SCHEDULER_SECRET}" \
  --attempt-deadline 120s
```

### IV snapshots (4:30 PM ET, weekdays)

Writes one IV snapshot per `earnings-candidate`-tagged watchlist ticker
into `iv_snapshots`. Runs 30 minutes after market close so end-of-day IV
is settled.

```bash
gcloud scheduler jobs create http earnings-refresh-snapshots \
  --location us-central1 \
  --schedule "30 16 * * 1-5" \
  --time-zone "America/New_York" \
  --uri "${SERVICE_URL}/api/internal/earnings/refresh-snapshots" \
  --http-method POST \
  --headers "X-Scheduler-Secret=${SCHEDULER_SECRET}" \
  --attempt-deadline 120s
```

### Earnings alert checks (5 PM ET, weekdays)

Evaluates active `earnings_iv` alerts against the freshly-written
snapshots. Runs after `earnings-refresh-snapshots` has had a chance to
complete.

```bash
gcloud scheduler jobs create http earnings-run-alert-checks \
  --location us-central1 \
  --schedule "0 17 * * 1-5" \
  --time-zone "America/New_York" \
  --uri "${SERVICE_URL}/api/internal/alerts/run-earnings-checks" \
  --http-method POST \
  --headers "X-Scheduler-Secret=${SCHEDULER_SECRET}" \
  --attempt-deadline 60s
```

### One-day smoke (after first deploy)

After provisioning the three jobs, tag at least one watchlist item with
the `earnings-candidate` tag so the snapshot job has work to do, then
wait one full ET day cycle and verify:

```bash
# All three jobs succeeded most recently
gcloud scheduler jobs list --location us-central1 \
  --filter "name~earnings" \
  --format "table(name, state, lastAttemptTime, status.code)"

# Tail recent invocation logs
gcloud logging read \
  'resource.type=cloud_scheduler_job AND resource.labels.job_id~earnings' \
  --limit 20 --format "value(timestamp, resource.labels.job_id, jsonPayload.status)"
```

Acceptance: each job returns 2xx; at least one row in `earnings_events`
and `iv_snapshots`; no error rows in `alert_history` for alert_type
`earnings_iv` (zero rows is acceptable if no matching alerts exist yet).

---

## 5. Verify Deployment

```bash
# Check service is running
curl ${SERVICE_URL}/api/health

# Check database connection
curl ${SERVICE_URL}/api/health/db

# Check internal endpoint (with secret)
curl -X POST ${SERVICE_URL}/api/internal/health \
  -H "X-Scheduler-Secret: ${SCHEDULER_SECRET}"
```

---

## Environment Variables Reference

| Variable | Description | Required |
|----------|-------------|----------|
| `NEON_DATABASE_URL` | Postgres connection string | Yes |
| `FMP_API_KEY` | Financial Modeling Prep API key | Yes |
| `FINNHUB_API_KEY` | Finnhub API key (earnings calendar) | Yes (earnings) |
| `TASTYTRADE_CLIENT_SECRET` | Tastytrade OAuth2 app client secret | Yes (earnings) |
| `TASTYTRADE_REFRESH_TOKEN` | Tastytrade OAuth2 refresh token (never expires) | Yes (earnings) |
| `PUSHOVER_USER_KEY` | Pushover user key for notifications | Yes |
| `PUSHOVER_API_TOKEN` | Pushover app token | Yes |
| `SCHEDULER_SECRET` | Secret for internal endpoints | Yes |
| `AUTH_USERNAME` | Basic auth username for web access | Yes (prod) |
| `AUTH_PASSWORD` | Basic auth password for web access | Yes (prod) |
| `ENVIRONMENT` | `development` or `production` | No (default: development) |
| `PORT` | Server port (Cloud Run sets this) | No (default: 8080) |

---

## Updating

Push to `main` branch triggers Cloud Build (if connected), or:

```bash
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/danecast-trades
gcloud run deploy danecast-trades --image gcr.io/YOUR_PROJECT_ID/danecast-trades --region us-central1
```

---

## Costs (Estimated)

- **Cloud Run**: Scales to zero, ~$0 when idle. With light usage, < $5/month.
- **Cloud Scheduler**: 3 free jobs, then $0.10/job/month. ~$0.40/month for 7 jobs.
- **Secret Manager**: 6 free active secrets, then $0.06/secret/month. ~$0.
- **Neon Postgres**: Free tier includes 0.5 GB storage, 3 GB transfer.
- **Total**: Likely < $5/month for single-user usage.
