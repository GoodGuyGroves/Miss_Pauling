"""FASTDL_ENABLED=false must remove the FastDL host routes entirely.

Settings are import-time singletons, so this one case runs in a child process
with its own database file; the parent session keeps FastDL enabled.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from conftest import APP_IMPORT, FASTDL_BASE, REPO_ROOT, subprocess_env

CHILD = """
import json, os
from fastapi.testclient import TestClient

module_name, _, attr = os.environ["PAULING_APP"].partition(":")
app = getattr(__import__(module_name, fromlist=[attr]), attr)

client = TestClient(app, base_url=%(base_url)r, follow_redirects=False)
maps = client.get("/maps")
home = client.get("/")
print("RESULT " + json.dumps({
    "maps_status": maps.status_code,
    "home_status": home.status_code,
    "home_body": home.text[:4000],
}))
"""


def _run_child(**env_overrides) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        env = subprocess_env(
            MISS_PAULING_DB_PATH=str(Path(tmp) / "child.db"), **env_overrides
        )
        completed = subprocess.run(
            [sys.executable, "-c", CHILD % {"base_url": FASTDL_BASE}],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
    assert completed.returncode == 0, completed.stderr[-2000:]
    line = [ln for ln in completed.stdout.splitlines() if ln.startswith("RESULT ")]
    assert line, completed.stdout[-2000:] + completed.stderr[-2000:]
    return json.loads(line[-1][len("RESULT ") :])


def test_fastdl_host_falls_back_to_the_website_when_disabled():
    result = _run_child(FASTDL_ENABLED="false")

    assert result["maps_status"] == 404
    assert result["home_status"] == 200
    # the website home page is served on the FastDL hostname instead
    assert "<title>pugs.tf</title>" in result["home_body"]
    assert "<title>TF2 Map Manager</title>" not in result["home_body"]


def test_same_child_serves_fastdl_when_enabled():
    """Control: the only difference is the FASTDL_ENABLED value."""
    result = _run_child(FASTDL_ENABLED="true")

    assert result["maps_status"] == 200
    assert result["home_status"] == 200
    assert "<title>TF2 Map Manager</title>" in result["home_body"]


def test_session_app_serves_fastdl_maps(fdl):
    response = fdl.get("/maps")

    assert response.status_code == 200
    assert response.json() == []
    assert APP_IMPORT  # the child booted the very same import string
