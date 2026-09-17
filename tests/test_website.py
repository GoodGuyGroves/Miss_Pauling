"""Website host (https://www.pugs.tf) behaviour — spec bullets 1-6 and 8."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

import pytest

from conftest import DISCORD_CALLBACK_URL, auth, b64url_json


# --- 1. home page ---------------------------------------------------------
def test_home_anonymous_offers_discord_login_and_hides_server_browser(web):
    response = web.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "/auth/discord/login" in response.text
    assert "Server Browser" not in response.text


def test_home_is_html_document_titled_pugs_tf(web):
    body = web.get("/").text

    assert body.lstrip().lower().startswith("<!doctype html")
    assert "<title>pugs.tf</title>" in body


# --- 2. health probe ------------------------------------------------------
def test_healthz_reports_ok(web):
    response = web.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# --- 3. static assets -----------------------------------------------------
def test_static_app_js_is_served_as_javascript(web):
    response = web.get("/static/js/app.js")

    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
    assert len(response.content) > 0


def test_missing_static_asset_is_404(web):
    assert web.get("/static/js/does-not-exist.js").status_code == 404


# --- 4. profile -----------------------------------------------------------
def test_profile_anonymous_redirects_home_with_error(web):
    response = web.get("/profile")

    assert response.status_code == 307
    location = response.headers["location"]
    parsed = urlparse(location)
    assert parsed.path == "/"
    assert "error" in parse_qs(parsed.query)


def test_profile_with_session_shows_own_name(web, make_user):
    user = make_user("user")

    response = web.get("/profile", headers=auth(user.token))

    assert response.status_code == 200
    assert user.name in response.text


def test_profile_rejects_unknown_session_token(web):
    response = web.get("/profile", headers=auth("not-a-real-token"))

    assert response.status_code == 307
    assert urlparse(response.headers["location"]).path == "/"


# --- 5. admin pages -------------------------------------------------------
@pytest.mark.parametrize("path", ["/admin/", "/admin/users"])
def test_admin_pages_reject_plain_user_with_403(web, make_user, path):
    user = make_user("user")

    response = web.get(path, headers=auth(user.token))

    assert response.status_code == 403
    assert response.json()["detail"] == "Admin privileges required"


@pytest.mark.parametrize("path", ["/admin/", "/admin/users"])
def test_admin_pages_reject_anonymous_with_401(web, path):
    response = web.get(path)

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication required"


@pytest.mark.parametrize("path", ["/admin/", "/admin/users"])
def test_admin_pages_reject_bogus_session_with_401(web, path):
    response = web.get(path, headers=auth("not-a-real-token"))

    assert response.status_code == 401


def test_admin_pages_allow_moderator_and_show_their_name(web, make_user):
    moderator = make_user("user", "moderator")

    dashboard = web.get("/admin/", headers=auth(moderator.token))
    users_page = web.get("/admin/users", headers=auth(moderator.token))

    assert dashboard.status_code == 200
    assert moderator.name in dashboard.text
    assert users_page.status_code == 200
    assert moderator.name in users_page.text


def test_admin_users_page_does_not_link_to_logs(web, make_user):
    moderator = make_user("user", "moderator")

    users_page = web.get("/admin/users", headers=auth(moderator.token))

    assert users_page.status_code == 200
    assert "/admin/logs" not in users_page.text


def test_admin_logs_route_is_gone(web, make_user):
    moderator = make_user("user", "moderator")

    assert web.get("/admin/logs", headers=auth(moderator.token)).status_code == 404
    assert web.get("/admin/logs").status_code == 404


# --- 6. session validation API -------------------------------------------
def test_validate_session_requires_cookie(web):
    response = web.get("/api/validate/session")

    assert response.status_code == 401


def test_validate_session_rejects_bogus_token(web):
    assert web.get("/api/validate/session", headers=auth("nope")).status_code == 401


def test_validate_session_returns_identity_and_roles(web, make_user):
    user = make_user("user", "helper")

    response = web.get("/api/validate/session", headers=auth(user.token))

    assert response.status_code == 200
    payload = response.json()
    assert payload["user_id"] == user.id
    assert payload["name"] == user.name
    assert payload["is_authenticated"] is True
    assert isinstance(payload["roles"], list)
    assert all(isinstance(role, str) for role in payload["roles"])
    assert set(payload["roles"]) == {"user", "helper"}


def test_validate_session_roles_track_assignment(web, make_user):
    plain = make_user("user")
    admin = make_user("user", "administrator")

    plain_roles = web.get("/api/validate/session", headers=auth(plain.token)).json()["roles"]
    admin_roles = web.get("/api/validate/session", headers=auth(admin.token)).json()["roles"]

    assert set(plain_roles) == {"user"}
    assert "administrator" in admin_roles
    assert "administrator" not in plain_roles


# --- 8. cross-host login redirect ----------------------------------------
def test_redirect_login_builds_discord_authorize_url_with_state(web):
    return_to = "https://fastdl.pugs.tf/login/callback"

    response = web.get("/auth/redirect-login", params={"return_to": return_to})

    assert response.status_code == 307
    location = response.headers["location"]
    parsed = urlparse(location)
    assert parsed.netloc == "discord.com"
    query = parse_qs(parsed.query)
    assert query["client_id"] == ["1"]
    assert query["redirect_uri"] == [DISCORD_CALLBACK_URL]
    state = b64url_json(query["state"][0])
    assert state["return_to"] == return_to


def test_redirect_login_state_round_trips_the_requested_return_to(web):
    first = "https://fastdl.pugs.tf/login/callback"
    second = "https://fastdl.localhost/login/callback"

    def state_of(return_to):
        location = web.get(
            "/auth/redirect-login", params={"return_to": return_to}
        ).headers["location"]
        return b64url_json(parse_qs(urlparse(location).query)["state"][0])["return_to"]

    assert state_of(first) == first
    assert state_of(second) == second
    assert state_of(first) != state_of(second)


def test_discord_login_route_redirects_to_discord(web):
    response = web.get("/auth/discord/login")

    assert response.status_code == 307
    assert re.match(r"^https://discord\.com/", response.headers["location"])
