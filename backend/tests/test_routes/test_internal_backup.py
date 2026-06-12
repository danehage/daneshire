"""
Tests for the POST /api/internal/db/backup endpoint.

The backup service and Pushover are mocked at the module level so
these tests exercise HTTP concerns (auth, response shape, error
propagation) without touching the filesystem, pg_dump, or GCS.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.config import settings
from app.services.backup import BackupResult

TEST_SECRET = "test-scheduler-secret"


@pytest.fixture(autouse=True)
async def set_scheduler_secret():
    original = settings.scheduler_secret
    settings.scheduler_secret = TEST_SECRET
    yield
    settings.scheduler_secret = original


def _auth():
    return {"X-Scheduler-Secret": TEST_SECRET}


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_backup_requires_secret(client: AsyncClient):
    resp = await client.post("/api/internal/db/backup")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_backup_rejects_wrong_secret(client: AsyncClient):
    resp = await client.post(
        "/api/internal/db/backup", headers={"X-Scheduler-Secret": "wrong"}
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Configuration guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_backup_no_bucket_returns_400(client: AsyncClient):
    original = settings.gcs_backup_bucket
    settings.gcs_backup_bucket = ""
    try:
        resp = await client.post("/api/internal/db/backup", headers=_auth())
    finally:
        settings.gcs_backup_bucket = original

    assert resp.status_code == 400
    assert "GCS_BACKUP_BUCKET" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_backup_success(client: AsyncClient):
    original = settings.gcs_backup_bucket
    settings.gcs_backup_bucket = "test-bucket"
    try:
        fake = BackupResult(
            success=True,
            filename="danecast-2026-06-12.dump",
            gcs_path="gs://test-bucket/danecast-2026-06-12.dump",
            size_bytes=1_048_576,
            duration_seconds=3.2,
        )
        with patch("app.routes.internal.run_backup", new=AsyncMock(return_value=fake)):
            resp = await client.post("/api/internal/db/backup", headers=_auth())
    finally:
        settings.gcs_backup_bucket = original

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["filename"] == "danecast-2026-06-12.dump"
    assert data["gcs_path"] == "gs://test-bucket/danecast-2026-06-12.dump"
    assert data["size_bytes"] == 1_048_576
    assert data["error"] is None


# ---------------------------------------------------------------------------
# Failure path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_backup_failure_returns_500(client: AsyncClient):
    original = settings.gcs_backup_bucket
    settings.gcs_backup_bucket = "test-bucket"
    try:
        fake = BackupResult(
            success=False,
            filename="danecast-2026-06-12.dump",
            gcs_path="gs://test-bucket/danecast-2026-06-12.dump",
            size_bytes=0,
            duration_seconds=0.1,
            error="pg_dump: command not found",
        )
        with patch("app.routes.internal.run_backup", new=AsyncMock(return_value=fake)):
            with patch("app.routes.internal.PushoverClient") as mock_cls:
                mock_pushover = MagicMock()
                mock_pushover.is_configured = False
                mock_cls.return_value = mock_pushover

                resp = await client.post("/api/internal/db/backup", headers=_auth())
    finally:
        settings.gcs_backup_bucket = original

    assert resp.status_code == 500
    assert "Backup failed" in resp.json()["detail"]
    assert "pg_dump: command not found" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_backup_failure_sends_pushover_when_configured(client: AsyncClient):
    original = settings.gcs_backup_bucket
    settings.gcs_backup_bucket = "test-bucket"
    try:
        fake = BackupResult(
            success=False,
            filename="danecast-2026-06-12.dump",
            gcs_path="gs://test-bucket/danecast-2026-06-12.dump",
            size_bytes=0,
            duration_seconds=0.1,
            error="connection refused",
        )
        with patch("app.routes.internal.run_backup", new=AsyncMock(return_value=fake)):
            with patch("app.routes.internal.PushoverClient") as mock_cls:
                mock_pushover = MagicMock()
                mock_pushover.is_configured = True
                mock_pushover.send = AsyncMock(return_value=True)
                mock_pushover.close = AsyncMock()
                mock_cls.return_value = mock_pushover

                resp = await client.post("/api/internal/db/backup", headers=_auth())
    finally:
        settings.gcs_backup_bucket = original

    assert resp.status_code == 500
    mock_pushover.send.assert_awaited_once()
    call_kwargs = mock_pushover.send.call_args.kwargs
    assert call_kwargs["priority"] == "high"
    assert "connection refused" in call_kwargs["message"]


@pytest.mark.asyncio
async def test_backup_failure_no_pushover_when_not_configured(client: AsyncClient):
    """No Pushover call when credentials are absent (development env)."""
    original = settings.gcs_backup_bucket
    settings.gcs_backup_bucket = "test-bucket"
    try:
        fake = BackupResult(
            success=False,
            filename="danecast-2026-06-12.dump",
            gcs_path="gs://test-bucket/danecast-2026-06-12.dump",
            size_bytes=0,
            duration_seconds=0.1,
            error="some error",
        )
        with patch("app.routes.internal.run_backup", new=AsyncMock(return_value=fake)):
            with patch("app.routes.internal.PushoverClient") as mock_cls:
                mock_pushover = MagicMock()
                mock_pushover.is_configured = False
                mock_pushover.send = AsyncMock()
                mock_cls.return_value = mock_pushover

                resp = await client.post("/api/internal/db/backup", headers=_auth())
    finally:
        settings.gcs_backup_bucket = original

    assert resp.status_code == 500
    mock_pushover.send.assert_not_awaited()
