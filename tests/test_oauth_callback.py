"""Website Discord OAuth callback (GET /auth/discord/callback).

Only the outbound Discord token/profile exchange is faked (patched on the module
named by PAULING_AUTH_SERVICE_MODULE); everything else — user creation, role
assignment, the session cookie, the cross-host redirect — is exercised for real
over HTTP.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest

from conftest import (
    COOKIE_DOMAIN,
    FASTDL_LOGIN_CALLBACK,
    SESSION_COOKIE,
    auth,
    cookie_value,
    session_cookie_header,
)


def _state_for(web, return_to: str) -> str:
    location = web.get("/auth/redirect-login", params={"return_to": return_to}).headers[
        "location"
    ]
    return parse_qs(urlparse(location).query)["state"][0]


# --- (a) state-carrying callback returns to FastDL, cookie only ----------
def test_callback_with_state_redirects_to_fastdl_without_leaking_the_token(
    web, fake_discord_login
):
    fake_discord_login(username="Cbot")
    state = _state_for(web, FASTDL_LOGIN_CALLBACK)

    response = web.get("/auth/discord/callback", params={"code": "auth-code", "state": state})

    assert response.status_code == 307
    location = response.headers["location"]
    assert location == FASTDL_LOGIN_CALLBACK
    assert "session_token" not in location
    assert urlparse(location).query == ""


def test_callback_with_state_sets_the_shared_session_cookie(web, fake_discord_login):
    fake_discord_login(username="Cbot")
    state = _state_for(web, FASTDL_LOGIN_CALLBACK)

    response = web.get("/auth/discord/callback", params={"code": "auth-code", "state": state})

    header = session_cookie_header(response)
    assert header is not None, response.headers.get_list("set-cookie")
    assert f"Domain={COOKIE_DOMAIN}" in header
    assert "Secure" in header
    assert "HttpOnly" in header
    assert "Path=/" in header
    assert cookie_value(response, SESSION_COOKIE)


def test_callback_passes_the_authorization_code_to_the_exchange(web, fake_discord_login):
    identity = fake_discord_login(username="Cbot")
    state = _state_for(web, FASTDL_LOGIN_CALLBACK)

    web.get("/auth/discord/callback", params={"code": "code-12345", "state": state})

    assert identity.codes_seen == ["code-12345"]


# --- (b) the issued cookie works on both hosts ---------------------------
def test_cookie_from_callback_authenticates_on_website_and_fastdl(
    web, fdl, fake_discord_login
):
    identity = fake_discord_login(username="Cbot")
    state = _state_for(web, FASTDL_LOGIN_CALLBACK)

    callback = web.get(
        "/auth/discord/callback", params={"code": "auth-code", "state": state}
    )
    token = cookie_value(callback, SESSION_COOKIE)

    validated = web.get("/api/validate/session", headers=auth(token))
    assert validated.status_code == 200
    payload = validated.json()
    assert payload["name"] == "Cbot"
    assert payload["discord_id"] == identity.discord_id
    assert payload["is_authenticated"] is True

    fastdl_home = fdl.get("/", headers=auth(token))
    assert fastdl_home.status_code == 200
    assert "Welcome, Cbot" in fastdl_home.text
    assert "Welcome," not in fdl.get("/").text


# --- (c) no state -> home with a success message, same cookie ------------
def test_callback_without_state_redirects_home_with_success(web, fake_discord_login):
    fake_discord_login(username="Cbot")

    response = web.get("/auth/discord/callback", params={"code": "auth-code"})

    assert response.status_code == 307
    parsed = urlparse(response.headers["location"])
    assert parsed.path == "/"
    assert "success" in parse_qs(parsed.query)
    assert "error" not in parse_qs(parsed.query)
    header = session_cookie_header(response)
    assert header is not None
    assert f"Domain={COOKIE_DOMAIN}" in header
    assert "Secure" in header
    assert "HttpOnly" in header
    assert web.get(
        "/api/validate/session", headers=auth(cookie_value(response, SESSION_COOKIE))
    ).status_code == 200


# --- (d) new accounts get the "user" role --------------------------------
def test_user_created_by_callback_has_the_user_role(web, fake_discord_login):
    fake_discord_login(username="Cbot")

    response = web.get("/auth/discord/callback", params={"code": "auth-code"})
    token = cookie_value(response, SESSION_COOKIE)

    roles = web.get("/api/validate/session", headers=auth(token)).json()["roles"]
    assert roles == ["user"]


def test_user_created_by_callback_is_not_an_admin(web, fake_discord_login):
    fake_discord_login(username="Cbot")

    token = cookie_value(
        web.get("/auth/discord/callback", params={"code": "auth-code"}), SESSION_COOKIE
    )

    assert web.get("/admin/", headers=auth(token)).status_code == 403


# --- repeat logins reuse the same account --------------------------------
def test_logging_in_twice_reuses_the_same_account_with_a_fresh_session(
    web, fake_discord_login
):
    identity = fake_discord_login(username="Cbot")

    first = web.get("/auth/discord/callback", params={"code": "code-1"})
    second = web.get("/auth/discord/callback", params={"code": "code-2"})
    first_token = cookie_value(first, SESSION_COOKIE)
    second_token = cookie_value(second, SESSION_COOKIE)

    assert first_token != second_token
    first_user = web.get("/api/validate/session", headers=auth(first_token)).json()
    second_user = web.get("/api/validate/session", headers=auth(second_token)).json()
    assert first_user["user_id"] == second_user["user_id"]
    assert second_user["discord_id"] == identity.discord_id


def test_two_different_discord_identities_get_different_accounts(web, fake_discord_login):
    fake_discord_login(username="Cbot")
    first = cookie_value(
        web.get("/auth/discord/callback", params={"code": "c1"}), SESSION_COOKIE
    )
    fake_discord_login(username="Dbot")
    second = cookie_value(
        web.get("/auth/discord/callback", params={"code": "c2"}), SESSION_COOKIE
    )

    first_user = web.get("/api/validate/session", headers=auth(first)).json()
    second_user = web.get("/api/validate/session", headers=auth(second)).json()

    assert first_user["name"] == "Cbot"
    assert second_user["name"] == "Dbot"
    assert first_user["user_id"] != second_user["user_id"]


# --- failure path ---------------------------------------------------------
def test_callback_without_code_is_rejected(web, fake_discord_login):
    fake_discord_login(username="Cbot")

    response = web.get("/auth/discord/callback")

    assert response.status_code == 422
    assert session_cookie_header(response) is None


@pytest.mark.parametrize("state", ["not-base64", "Zm9vYmFy"])
def test_callback_with_unusable_state_falls_back_to_home(web, fake_discord_login, state):
    fake_discord_login(username="Cbot")

    response = web.get("/auth/discord/callback", params={"code": "auth-code", "state": state})

    assert response.status_code == 307
    assert urlparse(response.headers["location"]).path == "/"
