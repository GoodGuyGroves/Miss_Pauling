"""Black-box test harness for the Miss Pauling ASGI app.

The package layout is expected to change, so NOTHING in this suite imports a
project module by a hard-coded name.  Five environment variables carry the
import paths; the defaults below describe the CURRENT layout and are the only
place that needs editing after a restructure:

    PAULING_APP                  default "pauling.main:app"
                                 -> the ASGI app object
    PAULING_DB_MODULE            default "pauling.db.database"
                                 -> exposes `engine`
    PAULING_REPO_MODULE          default "pauling.db.repositories"
                                 -> exposes `UserRepository`
    PAULING_MODELS_MODULE        default "pauling.db.models"
                                 -> exposes the `User` model
    PAULING_AUTH_SERVICE_MODULE  default "pauling.services.auth_service"
                                 -> exposes `exchange_discord_code` (async) and
                                    `DiscordUserResponse`; patched in tests so
                                    the OAuth callback makes no network call

Everything else goes over HTTP through fastapi.testclient.TestClient.  The app
routes by Host header: `https://www.pugs.tf` reaches the website and
`https://fastdl.pugs.tf` reaches the FastDL sub-application.
"""

from __future__ import annotations

import base64
import importlib
import json
import os
import shutil
import sys
import tempfile
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

APP_IMPORT = os.environ.setdefault("PAULING_APP", "pauling.main:app")
DB_MODULE = os.environ.setdefault("PAULING_DB_MODULE", "pauling.db.database")
REPO_MODULE = os.environ.setdefault("PAULING_REPO_MODULE", "pauling.db.repositories")
MODELS_MODULE = os.environ.setdefault("PAULING_MODELS_MODULE", "pauling.db.models")
AUTH_SERVICE_MODULE = os.environ.setdefault(
    "PAULING_AUTH_SERVICE_MODULE", "pauling.services.auth_service"
)

# --------------------------------------------------------------------------
# Constants the tests assert against (mirror the generated settings below).
# --------------------------------------------------------------------------
WEBSITE_BASE = "https://www.pugs.tf"
FASTDL_BASE = "https://fastdl.pugs.tf"
FASTDL_ALT_BASE = "http://fastdl.localhost"
COOKIE_DOMAIN = ".pugs.tf"
SESSION_COOKIE = "session_token"
CSRF_COOKIE = "csrf_token"
MAPCYCLES = ["pt_official", "pt_all"]
MAX_MAP_MB = 1
DISCORD_CALLBACK_URL = "https://www.pugs.tf/auth/discord/callback"
FASTDL_LOGIN_CALLBACK = "https://fastdl.pugs.tf/login/callback"

# --------------------------------------------------------------------------
# Environment must be complete BEFORE the app module is imported: the app
# reads its settings once, at import time, into module-level singletons.
# --------------------------------------------------------------------------
_TMP = Path(tempfile.mkdtemp(prefix="pauling-tests-"))
MAPS_DIR = _TMP / "maps"
MAPS_DIR.mkdir(parents=True, exist_ok=True)
MAPCYCLE_STATE_FILE = _TMP / "mapcycle.json"

_WEBSITE_SETTINGS = {
    "DISCORD_APPLICATION_ID": "1",
    "DISCORD_PUBLIC_KEY": "x",
    "DISCORD_CALLBACK_URL": DISCORD_CALLBACK_URL,
    "STEAM_OPENID_REALM": WEBSITE_BASE,
    "STEAM_OPENID_CALLBACK_URL": "https://www.pugs.tf/auth/steam/callback",
}
_FASTDL_SETTINGS = {
    "hosts": ["fastdl.pugs.tf", "fastdl.localhost"],
    "maps_dir": str(MAPS_DIR),
    "allowed_map_extensions": [".bsp"],
    "max_map_file_size": MAX_MAP_MB,
    "mapcycles": list(MAPCYCLES),
    "mapcycle_state_file": str(MAPCYCLE_STATE_FILE),
    "website_base_url": WEBSITE_BASE,
}

_website_settings_file = _TMP / "website_settings.json"
_website_settings_file.write_text(json.dumps(_WEBSITE_SETTINGS))
_fastdl_settings_file = _TMP / "fastdl_settings.json"
_fastdl_settings_file.write_text(json.dumps(_FASTDL_SETTINGS))

APP_ENV = {
    "MISS_PAULING_API_SECRET_KEY": "test-secret-key",
    "STEAM_API_KEY": "test-steam-key",
    "DISCORD_CLIENT_SECRET": "test-discord-secret",
    "DISCORD_TOKEN": "test-discord-token",
    "environment": "production",
    "ENVIRONMENT": "production",
    "MISS_PAULING_DB_PATH": str(_TMP / "test.db"),
    "MISS_PAULING_COOKIE_DOMAIN": COOKIE_DOMAIN,
    "MISS_PAULING_SETTINGS_FILE": str(_website_settings_file),
    "FASTDL_SETTINGS_FILE": str(_fastdl_settings_file),
    "FASTDL_ENABLED": "true",
}
os.environ.update(APP_ENV)


def subprocess_env(**overrides) -> dict:
    """Environment for a child process that boots the app the way this session
    does, with `overrides` applied (e.g. FASTDL_ENABLED="false")."""
    env = dict(os.environ)
    env.update(APP_ENV)
    env.update(
        {
            "PAULING_APP": APP_IMPORT,
            "PYTHONPATH": os.pathsep.join(
                [str(REPO_ROOT)] + [p for p in os.environ.get("PYTHONPATH", "").split(os.pathsep) if p]
            ),
        }
    )
    env.update({key: str(value) for key, value in overrides.items()})
    return env


# --------------------------------------------------------------------------
# Thin wrappers around the configurable imports.
# --------------------------------------------------------------------------
def _import_attr(import_string: str):
    module_name, _, attr = import_string.partition(":")
    return getattr(importlib.import_module(module_name), attr)


@pytest.fixture(scope="session")
def app():
    """The ASGI application object, imported once per session."""
    return _import_attr(APP_IMPORT)


@pytest.fixture(scope="session")
def _session_factory(app):
    """SQLAlchemy sessionmaker bound to the app's own engine."""
    from sqlalchemy.orm import sessionmaker  # third-party, not a project module

    engine = getattr(importlib.import_module(DB_MODULE), "engine")
    return sessionmaker(bind=engine, expire_on_commit=False)


# --------------------------------------------------------------------------
# HTTP clients.
# --------------------------------------------------------------------------
def _new_client(app, base_url: str):
    from fastapi.testclient import TestClient

    return TestClient(app, base_url=base_url, follow_redirects=False)


@pytest.fixture
def web(app):
    """Client bound to the website host."""
    return _new_client(app, WEBSITE_BASE)


@pytest.fixture
def fdl(app):
    """Client bound to the FastDL host."""
    return _new_client(app, FASTDL_BASE)


@pytest.fixture
def client_for(app):
    """Factory: client_for("http://fastdl.localhost") -> TestClient."""

    def _factory(base_url: str):
        return _new_client(app, base_url)

    return _factory


def auth(token: str) -> dict:
    """Headers carrying a session cookie (no cookie jar => no cross-test leaks)."""
    return {"Cookie": f"{SESSION_COOKIE}={token}"}


def auth_with_csrf(session_token: str, csrf_token: str) -> dict:
    return {"Cookie": f"{SESSION_COOKIE}={session_token}; {CSRF_COOKIE}={csrf_token}"}


# --------------------------------------------------------------------------
# Users / sessions / roles, created straight through the app's own database.
# --------------------------------------------------------------------------
@pytest.fixture
def make_user(_session_factory):
    """Factory: make_user("helper") -> object with .id .name .discord_id .token"""
    repo = getattr(importlib.import_module(REPO_MODULE), "UserRepository")
    models = importlib.import_module(MODELS_MODULE)

    def _make(*roles: str, name: str | None = None):
        unique = uuid.uuid4().hex[:10]
        display_name = name or f"Tester{unique}"
        discord_id = str(uuid.uuid4().int)[:18]
        with _session_factory() as db:
            user = models.User(discord_id=discord_id, name=display_name)
            db.add(user)
            db.commit()
            db.refresh(user)
            for role_name in roles:
                repo.assign_role(db, user.id, role_name)
            session = repo.create_session(db, user.id, "discord")
            token = session.session_token
        return SimpleNamespace(
            id=user.id, name=display_name, discord_id=discord_id, token=token
        )

    return _make


# --------------------------------------------------------------------------
# Discord OAuth: the outbound call is replaced, nothing else is faked.
# --------------------------------------------------------------------------
@pytest.fixture
def fake_discord_login(monkeypatch):
    """Patch the auth service's outbound Discord exchange.

    Returns a callable: fake_discord_login(username="Cbot") -> the identity the
    callback will see (.discord_id, .username, .codes_seen).
    """
    module = importlib.import_module(AUTH_SERVICE_MODULE)
    discord_user_model = getattr(module, "DiscordUserResponse")

    def _install(username: str = "Cbot", discord_id: str | None = None, avatar=None):
        identity = SimpleNamespace(
            discord_id=discord_id or str(uuid.uuid4().int)[:18],
            username=username,
            codes_seen=[],
        )

        async def _fake_exchange(code: str):
            identity.codes_seen.append(code)
            return discord_user_model(
                id=identity.discord_id,
                username=identity.username,
                avatar=avatar,
                discriminator="0",
            )

        monkeypatch.setattr(module, "exchange_discord_code", _fake_exchange)
        return identity

    return _install


# --------------------------------------------------------------------------
# FastDL filesystem state: every test starts with an empty map store and no
# mapcycle memberships, so no test depends on another's leftovers.
# --------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def clean_fastdl_state():
    def _wipe():
        if MAPS_DIR.exists():
            shutil.rmtree(MAPS_DIR)
        MAPS_DIR.mkdir(parents=True, exist_ok=True)
        if MAPCYCLE_STATE_FILE.exists():
            MAPCYCLE_STATE_FILE.unlink()

    _wipe()
    yield
    _wipe()


@pytest.fixture
def map_bytes():
    """Deterministic pseudo-BSP payload of a requested size."""

    def _make(size: int = 2048, seed: bytes = b"VBSP") -> bytes:
        body = (seed + uuid.uuid4().bytes) * ((size // 20) + 1)
        return body[:size]

    return _make


@pytest.fixture
def upload_map(fdl, map_bytes):
    """Upload a .bsp through the app's own endpoint; returns (filename, bytes)."""

    def _upload(user, filename: str = "cp_orange_x3.bsp", size: int = 2048):
        payload = map_bytes(size)
        response = fdl.post(
            "/upload",
            files={"file": (filename, payload, "application/octet-stream")},
            headers=auth(user.token),
        )
        assert response.status_code == 200, response.text
        return filename, payload

    return _upload


@pytest.fixture
def place_file_in_map_store():
    """Drop a raw file into the map store (filesystem only, no app code)."""

    def _place(filename: str, content: bytes = b"not a map") -> str:
        (MAPS_DIR / filename).write_bytes(content)
        return filename

    return _place


# --------------------------------------------------------------------------
# Misc helpers.
# --------------------------------------------------------------------------
def b64url_json(value: str):
    """Decode a base64url-encoded JSON blob (OAuth `state`)."""
    padded = value + "=" * (-len(value) % 4)
    return json.loads(base64.urlsafe_b64decode(padded).decode())


def cookie_headers(response) -> list:
    return response.headers.get_list("set-cookie")


def _cookie_header(response, name: str) -> str | None:
    for header in cookie_headers(response):
        if header.startswith(f"{name}="):
            return header
    return None


def session_cookie_header(response) -> str | None:
    return _cookie_header(response, SESSION_COOKIE)


def cookie_value(response, name: str = SESSION_COOKIE) -> str | None:
    header = _cookie_header(response, name)
    if header is None:
        return None
    return header.split(";")[0].split("=", 1)[1].strip('"')
