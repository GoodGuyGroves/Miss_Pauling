"""FastDL host (https://fastdl.pugs.tf) behaviour — spec bullets 10-18."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

import pytest

from conftest import (
    FASTDL_ALT_BASE,
    MAPCYCLES,
    MAX_MAP_MB,
    WEBSITE_BASE,
    auth,
)

STYLESHEET_HREF_RE = re.compile(r'href="([^"]*styles\.css)"')


def _cycle_lines(fdl, cycle: str) -> list[str]:
    response = fdl.get(f"/tf/cfg/mapcycle_{cycle}.txt")
    assert response.status_code == 200
    return [line for line in response.text.splitlines() if line.strip()]


# --- 10. index page + stylesheet -----------------------------------------
def test_index_links_stylesheet_root_relative(fdl):
    response = fdl.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    hrefs = STYLESHEET_HREF_RE.findall(response.text)
    assert hrefs == ["/static/css/styles.css"]
    for href in hrefs:
        assert "http://fastdl" not in href
        assert "https://fastdl" not in href


def test_stylesheet_is_served_as_css(fdl):
    response = fdl.get("/static/css/styles.css")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/css")
    assert "body" in response.text


def test_alternate_host_serves_byte_identical_index(client_for, fdl):
    alt = client_for(FASTDL_ALT_BASE)

    alt_response = alt.get("/")
    primary_response = fdl.get("/")

    assert alt_response.status_code == 200
    assert primary_response.status_code == 200
    assert alt_response.content == primary_response.content
    assert b'href="/static/css/styles.css"' in alt_response.content


# --- 11. login handoff ----------------------------------------------------
def test_login_redirects_to_website_with_callback_return_to(fdl):
    response = fdl.get("/login")

    assert response.status_code == 307
    location = response.headers["location"]
    parsed = urlparse(location)
    assert f"{parsed.scheme}://{parsed.netloc}" == WEBSITE_BASE
    assert parsed.path == "/auth/redirect-login"
    assert parse_qs(parsed.query)["return_to"] == ["https://fastdl.pugs.tf/login/callback"]
    # the return_to must be urlencoded inside the query, not left raw
    assert "return_to=https%3A%2F%2Ffastdl.pugs.tf%2Flogin%2Fcallback" in location


# --- 12. greeting ---------------------------------------------------------
def test_index_greets_the_logged_in_user_only(fdl, make_user):
    user = make_user("user")

    anonymous = fdl.get("/")
    authenticated = fdl.get("/", headers=auth(user.token))

    assert f"Welcome, {user.name}" not in anonymous.text
    assert "Welcome," not in anonymous.text
    assert f"Welcome, {user.name}" in authenticated.text


# --- 13. map listing shape ------------------------------------------------
def test_maps_listing_is_empty_json_list_when_store_is_empty(fdl):
    response = fdl.get("/maps")

    assert response.status_code == 200
    assert response.json() == []


def test_maps_listing_items_describe_each_map(fdl, make_user, upload_map):
    helper = make_user("user", "helper")
    name, payload = upload_map(helper, "cp_orange_x3.bsp")

    response = fdl.get("/maps")

    assert response.status_code == 200
    items = response.json()
    assert [item["name"] for item in items] == ["cp_orange_x3.bsp"]
    item = items[0]
    assert item["size"] == len(payload)
    assert isinstance(item["modified"], (int, float))
    assert item["mapcycles"] == {"pt_official": False, "pt_all": False}
    assert set(item["mapcycles"]) == set(MAPCYCLES)


def test_maps_listing_ignores_non_bsp_files_in_the_store(
    fdl, make_user, upload_map, place_file_in_map_store
):
    helper = make_user("user", "helper")
    upload_map(helper, "cp_orange_x3.bsp")
    place_file_in_map_store("readme.txt", b"not a map")

    names = [item["name"] for item in fdl.get("/maps").json()]

    assert names == ["cp_orange_x3.bsp"]


# --- 14. upload -----------------------------------------------------------
def test_upload_then_list_then_download_round_trips_bytes(fdl, make_user, upload_map):
    helper = make_user("user", "helper")
    name, payload = upload_map(helper, "cp_process_f12.bsp", size=4096)

    listing = fdl.get("/maps").json()
    download = fdl.get("/tf/maps/cp_process_f12.bsp")

    assert [item["name"] for item in listing] == ["cp_process_f12.bsp"]
    assert download.status_code == 200
    assert download.content == payload


def test_upload_reports_success_with_filename_and_size(fdl, make_user, map_bytes):
    helper = make_user("user", "helper")
    payload = map_bytes(1500)

    response = fdl.post(
        "/upload",
        files={"file": ("koth_product_rcx.bsp", payload, "application/octet-stream")},
        headers=auth(helper.token),
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "success",
        "message": "Uploaded successfully!",
        "filename": "koth_product_rcx.bsp",
        "size": 1500,
    }


def test_uploading_same_name_twice_is_skipped_and_keeps_original_bytes(
    fdl, make_user, map_bytes
):
    helper = make_user("user", "helper")
    original = map_bytes(2048, seed=b"ORIG")
    replacement = map_bytes(3072, seed=b"NEW!")

    first = fdl.post(
        "/upload",
        files={"file": ("cp_gullywash_f9.bsp", original, "application/octet-stream")},
        headers=auth(helper.token),
    )
    second = fdl.post(
        "/upload",
        files={"file": ("cp_gullywash_f9.bsp", replacement, "application/octet-stream")},
        headers=auth(helper.token),
    )

    assert first.json()["status"] == "success"
    assert second.status_code == 200
    assert second.json()["status"] == "skipped"
    assert second.json()["filename"] == "cp_gullywash_f9.bsp"
    assert fdl.get("/tf/maps/cp_gullywash_f9.bsp").content == original
    assert len(fdl.get("/maps").json()) == 1


def test_upload_rejects_non_bsp_extension(fdl, make_user):
    helper = make_user("user", "helper")

    response = fdl.post(
        "/upload",
        files={"file": ("notes.txt", b"hello", "text/plain")},
        headers=auth(helper.token),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid file type. Only .bsp files are allowed."
    assert fdl.get("/maps").json() == []


def test_upload_rejects_file_over_size_limit(fdl, make_user, map_bytes):
    helper = make_user("user", "helper")
    oversized = map_bytes(MAX_MAP_MB * 1024 * 1024 + 1024)

    response = fdl.post(
        "/upload",
        files={"file": ("cp_toobig.bsp", oversized, "application/octet-stream")},
        headers=auth(helper.token),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == f"File too large. Maximum size is {MAX_MAP_MB}MB."
    assert fdl.get("/maps").json() == []
    assert fdl.get("/tf/maps/cp_toobig.bsp").status_code == 404


# --- 15. directory indexes ------------------------------------------------
def test_tf_index_links_cfg_and_maps(fdl):
    response = fdl.get("/tf/")

    assert response.status_code == 200
    assert 'href="cfg/"' in response.text
    assert 'href="maps/"' in response.text


def test_tf_maps_index_lists_uploaded_maps(fdl, make_user, upload_map):
    helper = make_user("user", "helper")
    upload_map(helper, "cp_orange_x3.bsp")

    response = fdl.get("/tf/maps/")

    assert response.status_code == 200
    assert 'href="cp_orange_x3.bsp"' in response.text
    assert 'href="cp_process_f12.bsp"' not in response.text


def test_tf_cfg_index_lists_every_configured_mapcycle(fdl):
    response = fdl.get("/tf/cfg/")

    assert response.status_code == 200
    assert 'href="mapcycle_pt_official.txt"' in response.text
    assert 'href="mapcycle_pt_all.txt"' in response.text
    assert 'href="mapcycle_nope.txt"' not in response.text


# --- 16. download safety --------------------------------------------------
def test_download_of_missing_map_is_404(fdl):
    response = fdl.get("/tf/maps/cp_nothing_here.bsp")

    assert response.status_code == 404
    assert response.json()["detail"] == "Map not found"


def test_download_of_non_bsp_file_in_store_is_forbidden(fdl, place_file_in_map_store):
    place_file_in_map_store("secrets.txt", b"top secret")

    response = fdl.get("/tf/maps/secrets.txt")

    assert response.status_code == 403
    assert "top secret" not in response.text


@pytest.mark.parametrize(
    "path",
    [
        "/tf/maps/../../etc/passwd",
        "/tf/maps/..%2f..%2fetc%2fpasswd",
        "/tf/maps/....//etc/passwd",
    ],
)
def test_path_traversal_never_serves_a_file(fdl, path):
    response = fdl.get(path)

    assert response.status_code == 404
    assert "root:" not in response.text


# --- 17. mapcycles --------------------------------------------------------
def test_mapcycle_file_starts_empty_and_is_plain_text(fdl):
    response = fdl.get("/tf/cfg/mapcycle_pt_all.txt")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert response.text.strip() == ""


def test_unknown_mapcycle_file_is_404(fdl):
    response = fdl.get("/tf/cfg/mapcycle_nope.txt")

    assert response.status_code == 404
    assert response.json()["detail"] == "Mapcycle not found"


def test_mapcycle_toggle_requires_authentication(fdl, make_user, upload_map):
    helper = make_user("user", "helper")
    upload_map(helper, "cp_orange_x3.bsp")

    response = fdl.post("/maps/cp_orange_x3.bsp/mapcycle", params={"name": "pt_all"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication required"
    assert _cycle_lines(fdl, "pt_all") == []


def test_mapcycle_toggle_forbidden_for_plain_user(fdl, make_user, upload_map):
    helper = make_user("user", "helper")
    plain = make_user("user")
    upload_map(helper, "cp_orange_x3.bsp")

    response = fdl.post(
        "/maps/cp_orange_x3.bsp/mapcycle",
        params={"name": "pt_all"},
        headers=auth(plain.token),
    )

    assert response.status_code == 403
    assert _cycle_lines(fdl, "pt_all") == []


@pytest.mark.parametrize("role", ["helper", "moderator"])
def test_mapcycle_toggle_adds_map_without_extension(fdl, make_user, upload_map, role):
    privileged = make_user("user", role)
    upload_map(privileged, "cp_orange_x3.bsp")

    response = fdl.post(
        "/maps/cp_orange_x3.bsp/mapcycle",
        params={"name": "pt_all"},
        headers=auth(privileged.token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["filename"] == "cp_orange_x3.bsp"
    assert body["mapcycle"] == "pt_all"
    assert body["in_mapcycle"] is True
    assert fdl.get("/tf/cfg/mapcycle_pt_all.txt").text == "cp_orange_x3\n"
    assert fdl.get("/tf/cfg/mapcycle_pt_official.txt").text == ""


def test_mapcycle_toggle_twice_is_identity(fdl, make_user, upload_map):
    helper = make_user("user", "helper")
    upload_map(helper, "cp_orange_x3.bsp")
    before = fdl.get("/tf/cfg/mapcycle_pt_all.txt").text

    first = fdl.post(
        "/maps/cp_orange_x3.bsp/mapcycle",
        params={"name": "pt_all"},
        headers=auth(helper.token),
    )
    middle = fdl.get("/tf/cfg/mapcycle_pt_all.txt").text
    second = fdl.post(
        "/maps/cp_orange_x3.bsp/mapcycle",
        params={"name": "pt_all"},
        headers=auth(helper.token),
    )

    assert first.json()["in_mapcycle"] is True
    assert middle == "cp_orange_x3\n"
    assert second.json()["in_mapcycle"] is False
    assert fdl.get("/tf/cfg/mapcycle_pt_all.txt").text == before == ""


def test_mapcycle_membership_is_reflected_in_maps_listing(fdl, make_user, upload_map):
    helper = make_user("user", "helper")
    upload_map(helper, "cp_orange_x3.bsp")

    fdl.post(
        "/maps/cp_orange_x3.bsp/mapcycle",
        params={"name": "pt_official"},
        headers=auth(helper.token),
    )
    item = fdl.get("/maps").json()[0]

    assert item["mapcycles"] == {"pt_official": True, "pt_all": False}


def test_mapcycles_are_independent_of_each_other(fdl, make_user, upload_map):
    helper = make_user("user", "helper")
    upload_map(helper, "cp_orange_x3.bsp")
    upload_map(helper, "koth_product_rcx.bsp")

    fdl.post(
        "/maps/cp_orange_x3.bsp/mapcycle",
        params={"name": "pt_all"},
        headers=auth(helper.token),
    )
    fdl.post(
        "/maps/koth_product_rcx.bsp/mapcycle",
        params={"name": "pt_official"},
        headers=auth(helper.token),
    )

    assert fdl.get("/tf/cfg/mapcycle_pt_all.txt").text == "cp_orange_x3\n"
    assert fdl.get("/tf/cfg/mapcycle_pt_official.txt").text == "koth_product_rcx\n"


def test_mapcycle_file_lists_one_map_per_line(fdl, make_user, upload_map):
    helper = make_user("user", "helper")
    upload_map(helper, "cp_orange_x3.bsp")
    upload_map(helper, "koth_product_rcx.bsp")
    for name in ("cp_orange_x3.bsp", "koth_product_rcx.bsp"):
        fdl.post(
            f"/maps/{name}/mapcycle", params={"name": "pt_all"}, headers=auth(helper.token)
        )

    body = fdl.get("/tf/cfg/mapcycle_pt_all.txt").text

    assert sorted(body.splitlines()) == ["cp_orange_x3", "koth_product_rcx"]
    assert ".bsp" not in body


def test_toggling_unknown_mapcycle_name_is_400(fdl, make_user, upload_map):
    helper = make_user("user", "helper")
    upload_map(helper, "cp_orange_x3.bsp")

    response = fdl.post(
        "/maps/cp_orange_x3.bsp/mapcycle",
        params={"name": "nope"},
        headers=auth(helper.token),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Unknown mapcycle: nope"


def test_toggling_unknown_map_is_404(fdl, make_user):
    helper = make_user("user", "helper")

    response = fdl.post(
        "/maps/cp_ghost.bsp/mapcycle", params={"name": "pt_all"}, headers=auth(helper.token)
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Map not found"
    assert _cycle_lines(fdl, "pt_all") == []


def test_toggling_non_bsp_file_is_400(fdl, make_user, place_file_in_map_store):
    helper = make_user("user", "helper")
    place_file_in_map_store("readme.txt")

    response = fdl.post(
        "/maps/readme.txt/mapcycle", params={"name": "pt_all"}, headers=auth(helper.token)
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid map file"
    assert _cycle_lines(fdl, "pt_all") == []


# --- 18. delete -----------------------------------------------------------
def test_delete_requires_authentication(fdl, make_user, upload_map):
    helper = make_user("user", "helper")
    upload_map(helper, "cp_orange_x3.bsp")

    response = fdl.delete("/maps/cp_orange_x3.bsp")

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication required"
    assert fdl.get("/tf/maps/cp_orange_x3.bsp").status_code == 200


def test_delete_forbidden_for_plain_user(fdl, make_user, upload_map):
    helper = make_user("user", "helper")
    plain = make_user("user")
    upload_map(helper, "cp_orange_x3.bsp")

    response = fdl.delete("/maps/cp_orange_x3.bsp", headers=auth(plain.token))

    assert response.status_code == 403
    assert fdl.get("/tf/maps/cp_orange_x3.bsp").status_code == 200


def test_helper_delete_removes_map_from_store_and_all_mapcycles(
    fdl, make_user, upload_map
):
    helper = make_user("user", "helper")
    upload_map(helper, "cp_orange_x3.bsp")
    upload_map(helper, "koth_product_rcx.bsp")
    for cycle in MAPCYCLES:
        for name in ("cp_orange_x3.bsp", "koth_product_rcx.bsp"):
            fdl.post(
                f"/maps/{name}/mapcycle",
                params={"name": cycle},
                headers=auth(helper.token),
            )

    response = fdl.delete("/maps/cp_orange_x3.bsp", headers=auth(helper.token))

    assert response.status_code == 200
    assert response.json() == {
        "status": "success",
        "filename": "cp_orange_x3.bsp",
        "message": "Map cp_orange_x3.bsp deleted successfully",
    }
    assert [item["name"] for item in fdl.get("/maps").json()] == ["koth_product_rcx.bsp"]
    assert fdl.get("/tf/maps/cp_orange_x3.bsp").status_code == 404
    assert fdl.get("/tf/cfg/mapcycle_pt_all.txt").text == "koth_product_rcx\n"
    assert fdl.get("/tf/cfg/mapcycle_pt_official.txt").text == "koth_product_rcx\n"


def test_deleting_missing_map_is_404(fdl, make_user):
    helper = make_user("user", "helper")

    response = fdl.delete("/maps/cp_ghost.bsp", headers=auth(helper.token))

    assert response.status_code == 404
    assert response.json()["detail"] == "Map not found"


def test_deleting_non_bsp_file_is_400(fdl, make_user, place_file_in_map_store):
    helper = make_user("user", "helper")
    place_file_in_map_store("readme.txt", b"keep me")

    response = fdl.delete("/maps/readme.txt", headers=auth(helper.token))

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid map file"
