"""
Nightly database backup service.

Runs ``pg_dump -Fc`` against the Neon production database and uploads the
result to a GCS bucket. Called from the ``POST /api/internal/db/backup``
endpoint which is triggered by Cloud Scheduler.

The heavy work (_do_backup) runs in a thread-pool executor so it does not
block the async event loop during the multi-second dump + upload.
"""

import asyncio
import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit

from google.cloud import storage

logger = logging.getLogger(__name__)

# Hard ceiling for pg_dump so a runaway process can't stall Cloud Run.
_PG_DUMP_TIMEOUT_SECONDS = 300


@dataclass
class BackupResult:
    success: bool
    filename: str
    gcs_path: str
    size_bytes: int
    duration_seconds: float
    error: str | None = None


def _pg_env(db_url: str) -> tuple[dict[str, str], str]:
    """Return ``(environ, dbname)`` suitable for passing to pg_dump.

    Strips the ``+asyncpg`` SQLAlchemy driver suffix and maps the URL
    components to PG* environment variables. SSL defaults to ``require``
    (Neon mandates it) unless the URL specifies otherwise.
    """
    clean = db_url.replace("+asyncpg", "")
    parsed = urlsplit(clean)

    env = os.environ.copy()
    if parsed.username:
        env["PGUSER"] = parsed.username
    if parsed.password:
        env["PGPASSWORD"] = parsed.password
    if parsed.hostname:
        env["PGHOST"] = parsed.hostname
    if parsed.port:
        env["PGPORT"] = str(parsed.port)

    qs = parse_qs(parsed.query)
    ssl_mode = (qs.get("sslmode") or qs.get("ssl") or ["require"])[0]
    env["PGSSLMODE"] = ssl_mode

    dbname = parsed.path.lstrip("/")
    return env, dbname


def _do_backup(db_url: str, gcs_bucket: str) -> BackupResult:
    """Synchronous worker — runs pg_dump then streams the file to GCS.

    Meant to be called via ``run_in_executor``. Returns a BackupResult
    regardless of outcome so the caller decides whether to surface an error.
    """
    start = datetime.now(timezone.utc)
    date_str = start.strftime("%Y-%m-%d")
    filename = f"danecast-{date_str}.dump"
    gcs_path = f"gs://{gcs_bucket}/{filename}"

    tmp_path: str | None = None
    try:
        pg_env, dbname = _pg_env(db_url)

        with tempfile.NamedTemporaryFile(suffix=".dump", delete=False) as tmp:
            tmp_path = tmp.name

        result = subprocess.run(
            ["pg_dump", "-Fc", "-f", tmp_path, dbname],
            env=pg_env,
            capture_output=True,
            text=True,
            timeout=_PG_DUMP_TIMEOUT_SECONDS,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"pg_dump exited {result.returncode}: {result.stderr.strip()}"
            )

        size = os.path.getsize(tmp_path)

        client = storage.Client()
        bucket = client.bucket(gcs_bucket)
        blob = bucket.blob(filename)
        blob.upload_from_filename(tmp_path)

        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        logger.info("Backup complete: %s (%d bytes, %.1fs)", gcs_path, size, elapsed)
        return BackupResult(
            success=True,
            filename=filename,
            gcs_path=gcs_path,
            size_bytes=size,
            duration_seconds=elapsed,
        )

    except Exception as exc:
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        logger.error("Backup failed after %.1fs: %s", elapsed, exc, exc_info=True)
        return BackupResult(
            success=False,
            filename=filename,
            gcs_path=gcs_path,
            size_bytes=0,
            duration_seconds=elapsed,
            error=str(exc),
        )
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


async def run_backup(db_url: str, gcs_bucket: str) -> BackupResult:
    """Run a full database backup, uploading to GCS. Non-blocking."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _do_backup, db_url, gcs_bucket)
