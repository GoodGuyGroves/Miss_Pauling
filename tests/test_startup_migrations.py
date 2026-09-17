"""Booting the app must bring its database to the latest Alembic revision.

Three cases, each in a child process with its own database file (settings and
the engine are import-time singletons):

1. An empty database ends up at the Alembic head after boot.
2. A database that predates Alembic (tables present, no alembic_version table)
   is stamped and stays healthy; boot must not try to re-create its tables.
3. Booting twice is idempotent.

`alembic` is only ever driven through its CLI here, from the repo root, so the
test does not depend on where the migrations package lives.
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from conftest import REPO_ROOT, subprocess_env

BOOT = """
import json, os, sqlite3
from fastapi.testclient import TestClient

module_name, _, attr = os.environ["PAULING_APP"].partition(":")
app = getattr(__import__(module_name, fromlist=[attr]), attr)
health = TestClient(app).get("/healthz").status_code

db = sqlite3.connect(os.environ["MISS_PAULING_DB_PATH"])
tables = sorted(r[0] for r in db.execute("select name from sqlite_master where type='table'"))
versions = [r[0] for r in db.execute("select version_num from alembic_version")] if "alembic_version" in tables else None
print("RESULT " + json.dumps({"health": health, "tables": tables, "versions": versions}))
"""


def _boot(db_path: Path, **overrides) -> dict:
    env = subprocess_env(MISS_PAULING_DB_PATH=str(db_path), FASTDL_ENABLED="false", **overrides)
    completed = subprocess.run(
        [sys.executable, "-c", BOOT], cwd=str(REPO_ROOT), env=env,
        capture_output=True, text=True, timeout=120,
    )
    assert completed.returncode == 0, completed.stderr[-3000:]
    line = [ln for ln in completed.stdout.splitlines() if ln.startswith("RESULT ")]
    assert line, completed.stdout[-2000:] + completed.stderr[-2000:]
    return json.loads(line[-1][len("RESULT "):])


def _alembic(db_path: Path, *args) -> subprocess.CompletedProcess:
    env = subprocess_env(MISS_PAULING_DB_PATH=str(db_path))
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args], cwd=str(REPO_ROOT), env=env,
        capture_output=True, text=True, timeout=120,
    )


def _head_revision() -> str:
    with tempfile.TemporaryDirectory() as tmp:
        out = _alembic(Path(tmp) / "unused.db", "heads")
    assert out.returncode == 0, out.stderr
    heads = [ln.split()[0] for ln in out.stdout.splitlines() if "(head)" in ln]
    assert len(heads) == 1, out.stdout
    return heads[0]


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "app.db"


def test_empty_database_is_migrated_to_head_on_boot(db_path):
    result = _boot(db_path)

    assert result["health"] == 200
    assert {"users", "roles", "user_roles", "user_sessions"} <= set(result["tables"])
    assert result["versions"] == [_head_revision()]

    check = _alembic(db_path, "check")
    assert check.returncode == 0, check.stdout + check.stderr


def test_database_from_before_alembic_is_stamped_not_recreated(db_path):
    # Produce a pre-Alembic database the black-box way: boot once, then remove
    # the version bookkeeping so the tables exist without any stamp.
    _boot(db_path)
    with sqlite3.connect(db_path) as db:
        db.execute("drop table alembic_version")

    result = _boot(db_path)

    assert result["health"] == 200
    assert result["versions"] == [_head_revision()], "pre-baseline database must be stamped at head"
    check = _alembic(db_path, "check")
    assert check.returncode == 0, check.stdout + check.stderr


def test_boot_is_idempotent_and_preserves_data(db_path):
    _boot(db_path)
    with sqlite3.connect(db_path) as db:
        db.execute(
            "insert into users (discord_id, name, created_at, last_login) "
            "values ('keep-me', 'Kept', '2026-01-01 00:00:00', '2026-01-01 00:00:00')"
        )
    before = _boot(db_path)
    after = _boot(db_path)

    assert before == after
    with sqlite3.connect(db_path) as db:
        assert db.execute("select count(*) from users where discord_id = 'keep-me'").fetchone()[0] == 1
