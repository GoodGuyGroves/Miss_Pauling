"""Cross-host behaviour: routing isolation, the shared session cookie, logout
propagation and role-hierarchy consistency — spec bullets 7, 9, 19 and 20."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest

from conftest import (
    COOKIE_DOMAIN,
    CSRF_COOKIE,
    FASTDL_ALT_BASE,
    SESSION_COOKIE,
    auth,
    auth_with_csrf,
    cookie_value,
    session_cookie_header,
)


# --- 7. host routing isolation -------------------------------------------
@pytest.mark.parametrize("path", ["/profile", "/admin/", "/api/validate/session", "/healthz"])
def test_website_routes_do_not_exist_on_fastdl_host(fdl, path):
    assert fdl.get(path).status_code == 404


@pytest.mark.parametrize("path", ["/maps", "/tf/", "/tf/cfg/mapcycle_pt_all.txt", "/upload"])
def test_fastdl_routes_do_not_exist_on_website_host(web, path):
    assert web.get(path).status_code == 404


def test_same_path_is_served_differently_per_host(web, fdl):
    website_home = web.get("/")
    fastdl_home = fdl.get("/")

    assert website_home.status_code == 200
    assert fastdl_home.status_code == 200
    assert "<title>pugs.tf</title>" in website_home.text
    assert "<title>TF2 Map Manager</title>" in fastdl_home.text


def test_alternate_fastdl_host_also_bypasses_the_website(client_for):
    alt = client_for(FASTDL_ALT_BASE)

    assert alt.get("/maps").status_code == 200
    assert alt.get("/profile").status_code == 404


# --- 9. session cookie attributes ----------------------------------------
def test_login_callback_sets_shared_session_cookie_with_hardened_attributes(
    fdl, make_user
):
    user = make_user("user")

    response = fdl.get("/login/callback", params={"session_token": user.token})

    assert response.status_code == 307
    header = session_cookie_header(response)
    assert header is not None, response.headers.get_list("set-cookie")
    assert header.startswith(f"{SESSION_COOKIE}={user.token}")
    assert f"Domain={COOKIE_DOMAIN}" in header
    assert "HttpOnly" in header
    assert "Secure" in header
    assert "SameSite=lax" in header.replace("SameSite=Lax", "SameSite=lax")
    assert "Path=/" in header


def test_cookie_issued_by_fastdl_authenticates_on_the_website(fdl, web, make_user):
    user = make_user("user")

    callback = fdl.get("/login/callback", params={"session_token": user.token})
    issued = session_cookie_header(callback).split(";")[0].split("=", 1)[1]

    validated = web.get("/api/validate/session", headers=auth(issued))
    assert validated.status_code == 200
    assert validated.json()["user_id"] == user.id


# --- 19. logout invalidates the session for both hosts -------------------
@pytest.mark.parametrize("method", ["post", "get"])
def test_logout_on_fastdl_clears_cookie_and_kills_the_shared_session(
    fdl, web, make_user, method
):
    user = make_user("user")
    assert web.get("/api/validate/session", headers=auth(user.token)).status_code == 200

    response = getattr(fdl, method)("/logout", headers=auth(user.token))

    assert response.status_code == 307
    header = session_cookie_header(response)
    assert header is not None
    assert f"Domain={COOKIE_DOMAIN}" in header
    assert 'session_token=""' in header or header.startswith(f"{SESSION_COOKIE}=;")
    assert "Max-Age=0" in header or "expires=" in header.lower()
    # the very same token must now be rejected on the website host too
    assert web.get("/api/validate/session", headers=auth(user.token)).status_code == 401
    assert fdl.get("/", headers=auth(user.token)).text.count(f"Welcome, {user.name}") == 0


def test_logout_does_not_affect_other_sessions(fdl, web, make_user):
    victim = make_user("user")
    bystander = make_user("user")

    fdl.post("/logout", headers=auth(victim.token))

    assert web.get("/api/validate/session", headers=auth(victim.token)).status_code == 401
    assert web.get("/api/validate/session", headers=auth(bystander.token)).status_code == 200


def test_logged_out_token_loses_fastdl_privileges(fdl, make_user, upload_map):
    helper = make_user("user", "helper")
    name, _ = upload_map(helper)

    fdl.post("/logout", headers=auth(helper.token))
    response = fdl.post(
        f"/maps/{name}/mapcycle", params={"name": "pt_all"}, headers=auth(helper.token)
    )

    assert response.status_code == 401


# --- 20. role hierarchy is consistent across hosts -----------------------
def test_captain_is_below_helper_on_both_hosts(fdl, web, make_user, upload_map):
    helper = make_user("user", "helper")
    captain = make_user("user", "captain")
    name, _ = upload_map(helper)

    toggle = fdl.post(
        f"/maps/{name}/mapcycle", params={"name": "pt_all"}, headers=auth(captain.token)
    )
    delete = fdl.delete(f"/maps/{name}", headers=auth(captain.token))
    admin = web.get("/admin/", headers=auth(captain.token))

    assert toggle.status_code == 403
    assert delete.status_code == 403
    assert admin.status_code == 403
    assert fdl.get(f"/tf/maps/{name}").status_code == 200


def test_superadmin_passes_on_both_hosts(fdl, web, make_user, upload_map):
    superadmin = make_user("user", "superadmin")
    name, _ = upload_map(superadmin)

    toggle = fdl.post(
        f"/maps/{name}/mapcycle", params={"name": "pt_all"}, headers=auth(superadmin.token)
    )
    admin = web.get("/admin/", headers=auth(superadmin.token))
    delete = fdl.delete(f"/maps/{name}", headers=auth(superadmin.token))

    assert toggle.status_code == 200
    assert toggle.json()["in_mapcycle"] is True
    assert admin.status_code == 200
    assert delete.status_code == 200
    assert fdl.get("/maps").json() == []


@pytest.mark.parametrize(
    "role, fastdl_ok, admin_ok",
    [
        ("user", False, False),
        ("captain", False, False),
        ("helper", True, False),
        ("moderator", True, True),
        ("administrator", True, True),
        ("superadmin", True, True),
    ],
)
def test_role_matrix_matches_on_both_hosts(
    fdl, web, make_user, upload_map, role, fastdl_ok, admin_ok
):
    helper = make_user("user", "helper")
    subject = make_user("user", role)
    name, _ = upload_map(helper)

    toggle = fdl.post(
        f"/maps/{name}/mapcycle", params={"name": "pt_all"}, headers=auth(subject.token)
    )
    admin = web.get("/admin/", headers=auth(subject.token))

    assert toggle.status_code == (200 if fastdl_ok else 403)
    assert admin.status_code == (200 if admin_ok else 403)


# --- website-side logout (POST with CSRF, and GET) -----------------------
def _csrf_for(web, token: str) -> str:
    home = web.get("/", headers=auth(token))
    assert home.status_code == 200
    csrf = cookie_value(home, CSRF_COOKIE)
    assert csrf, home.headers.get_list("set-cookie")
    return csrf


def test_website_logout_post_with_csrf_kills_the_session_on_both_hosts(
    web, fdl, make_user
):
    user = make_user("user")
    csrf = _csrf_for(web, user.token)

    response = web.post(
        "/auth/logout",
        data={"csrf_token": csrf},
        headers=auth_with_csrf(user.token, csrf),
    )

    assert response.status_code == 307
    parsed = urlparse(response.headers["location"])
    assert parsed.path == "/"
    assert "success" in parse_qs(parsed.query)
    header = session_cookie_header(response)
    assert header is not None and f"Domain={COOKIE_DOMAIN}" in header
    assert web.get("/api/validate/session", headers=auth(user.token)).status_code == 401
    assert f"Welcome, {user.name}" not in fdl.get("/", headers=auth(user.token)).text


def test_website_logout_post_without_valid_csrf_keeps_the_session(web, make_user):
    user = make_user("user")
    csrf = _csrf_for(web, user.token)

    response = web.post(
        "/auth/logout",
        data={"csrf_token": "wrong-" + csrf},
        headers=auth_with_csrf(user.token, csrf),
    )

    assert response.status_code == 307
    assert "error" in parse_qs(urlparse(response.headers["location"]).query)
    assert web.get("/api/validate/session", headers=auth(user.token)).status_code == 200


def test_website_logout_get_kills_the_session_on_both_hosts(web, fdl, make_user):
    user = make_user("user")
    assert fdl.get("/", headers=auth(user.token)).text.count(f"Welcome, {user.name}") == 1

    response = web.get("/auth/logout", headers=auth(user.token))

    assert response.status_code == 307
    assert urlparse(response.headers["location"]).path == "/"
    assert web.get("/api/validate/session", headers=auth(user.token)).status_code == 401
    assert f"Welcome, {user.name}" not in fdl.get("/", headers=auth(user.token)).text


def test_website_logout_leaves_other_sessions_alone(web, make_user):
    victim = make_user("user")
    bystander = make_user("user")

    web.get("/auth/logout", headers=auth(victim.token))

    assert web.get("/api/validate/session", headers=auth(victim.token)).status_code == 401
    assert web.get("/api/validate/session", headers=auth(bystander.token)).status_code == 200
