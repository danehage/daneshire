"""
Unit tests for the backup service.

All external calls (subprocess, GCS) are mocked so the suite runs without
pg_dump installed or GCS credentials available.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.services.backup import BackupResult, _do_backup, _pg_env


def test_pg_env_parses_asyncpg_url():
    url = "postgresql+asyncpg://user:pass@ep-host.us-east-2.aws.neon.tech/mydb?sslmode=require"
    env, dbname = _pg_env(url)

    assert env["PGUSER"] == "user"
    assert env["PGPASSWORD"] == "pass"
    assert env["PGHOST"] == "ep-host.us-east-2.aws.neon.tech"
    assert env["PGSSLMODE"] == "require"
    assert dbname == "mydb"


def test_pg_env_strips_asyncpg_driver():
    url = "postgresql+asyncpg://user:pass@host:5432/db"
    env, dbname = _pg_env(url)

    assert env["PGHOST"] == "host"
    assert env["PGPORT"] == "5432"
    assert dbname == "db"


def test_pg_env_defaults_ssl_to_require():
    url = "postgresql+asyncpg://user:pass@host/db"
    env, _ = _pg_env(url)

    assert env["PGSSLMODE"] == "require"


def test_pg_env_honours_ssl_query_param():
    url = "postgresql+asyncpg://user:pass@host/db?ssl=verify-full"
    env, _ = _pg_env(url)

    assert env["PGSSLMODE"] == "verify-full"


def test_do_backup_success():
    fake_size = 2048

    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stderr = ""

    mock_blob = MagicMock()
    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_gcs = MagicMock()
    mock_gcs.bucket.return_value = mock_bucket

    with patch("app.services.backup.subprocess.run", return_value=mock_proc):
        with patch("app.services.backup.storage.Client", return_value=mock_gcs):
            with patch("app.services.backup.os.path.getsize", return_value=fake_size):
                with patch("app.services.backup.os.unlink"):
                    result = _do_backup(
                        "postgresql+asyncpg://user:pass@host/db",
                        "test-bucket",
                    )

    assert result.success is True
    assert result.size_bytes == fake_size
    assert result.gcs_path.startswith("gs://test-bucket/danecast-")
    assert result.filename.endswith(".dump")
    assert result.error is None
    mock_blob.upload_from_filename.assert_called_once()


def test_do_backup_pg_dump_nonzero_exit():
    mock_proc = MagicMock()
    mock_proc.returncode = 1
    mock_proc.stderr = "FATAL: connection refused"

    with patch("app.services.backup.subprocess.run", return_value=mock_proc):
        with patch("app.services.backup.os.unlink"):
            result = _do_backup(
                "postgresql+asyncpg://user:pass@host/db",
                "test-bucket",
            )

    assert result.success is False
    assert result.error is not None
    assert "pg_dump exited 1" in result.error
    assert "connection refused" in result.error


def test_do_backup_gcs_auth_failure():
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stderr = ""

    with patch("app.services.backup.subprocess.run", return_value=mock_proc):
        with patch("app.services.backup.storage.Client", side_effect=Exception("no credentials")):
            with patch("app.services.backup.os.path.getsize", return_value=1024):
                with patch("app.services.backup.os.unlink"):
                    result = _do_backup(
                        "postgresql+asyncpg://user:pass@host/db",
                        "test-bucket",
                    )

    assert result.success is False
    assert result.error is not None
    assert "no credentials" in result.error


def test_do_backup_tmp_cleanup_on_failure():
    """Temp file is deleted even when an error occurs."""
    mock_proc = MagicMock()
    mock_proc.returncode = 1
    mock_proc.stderr = "error"

    unlink_calls: list = []

    with patch("app.services.backup.subprocess.run", return_value=mock_proc):
        with patch("app.services.backup.os.unlink", side_effect=unlink_calls.append):
            _do_backup("postgresql+asyncpg://user:pass@host/db", "bucket")

    # unlink should have been called with the temp file path
    assert len(unlink_calls) == 1
