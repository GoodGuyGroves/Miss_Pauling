# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this directory.

## Overview

`fastdl/` is the FastDL (Fast Download) map server and map-manager web UI for the TF2 servers. It is a standalone map store: maps are uploaded to and served from its own volume, and it never touches a game server's filesystem. Game servers point `sv_downloadurl` at it and can fetch their mapcycle files from it. It is **not a separate process**: `fastdl/app.py` defines a FastAPI sub-application that `website/app/main.py` mounts with Starlette host-based routing. Requests whose `Host` header matches one of the `hosts` in `fastdl/settings.json` (e.g. `fastdl.pugs.tf`) are served by this app; every other host is served by the website. One process, one container image, one database.

## Running

There is no standalone entry point. Run the website (from the repo root) and point a FastDL hostname at it:

```bash
uvicorn website.app.main:app --host 0.0.0.0 --port 8000 --reload
# then browse http://fastdl.localhost:8000/  (fastdl.localhost is in the default hosts list)
```

Set `FASTDL_ENABLED: false` in `website/settings.json` (or `.env`) to run the website without FastDL, e.g. when the map directories don't exist locally.

## Architecture

- **`app.py`**: the FastAPI sub-app with all FastDL routes
- **`core/config.py`**: Pydantic settings loaded from `fastdl/settings.json` (relative to this package, not the cwd; override with `FASTDL_SETTINGS_FILE`)
- **`core/auth.py`**: dependencies (`get_current_user`, `require_auth`, `require_helper_or_above`) built on the website's session and role helpers in `website/app/core/`. No HTTP round trip, no duplicated role hierarchy.
- **`core/mapcycle.py`**: mapcycle membership persisted in `mapcycle_state_file`; renders `mapcycle_{name}.txt` for `GET /tf/cfg/mapcycle_{name}.txt`
- **`core/tf2_versions.py`**: map version parsing for sorting
- **`templates/`, `static/`**: the map-manager UI

## Configuration (`settings.json`)

- `hosts`: hostnames routed to this sub-app
- `mapcycle_state_file`: where mapcycle membership is persisted (default `fastdl/mapcycle.json`; use a volume path in Kubernetes)
- `maps_dir`: directory maps are stored in and served from (created if missing; `/data/maps` in the container)
- `allowed_map_extensions`, `max_map_file_size` (MB), `mapcycles`
- `website_base_url`: used for the login redirect to the website's Discord OAuth flow

## Authentication

The session cookie is shared with the website. In production set `MISS_PAULING_COOKIE_DOMAIN` to `.pugs.tf` in the website settings so the cookie set on `www.pugs.tf` is sent to `fastdl.pugs.tf`. In development (no cookie domain) the website's OAuth callback appends the session token to the FastDL return URL and `/login/callback` sets it as a cookie on the FastDL host.

## API Endpoints

- `GET /`: Web interface
- `GET /maps`: List all maps with metadata
- `POST /upload`: Upload new map files
- `GET /tf/maps/{filename}`: Serve map files (FastDL)
- `GET /tf/cfg/mapcycle_{name}.txt`: Rendered mapcycle file for game servers to download
- `POST /maps/{filename}/mapcycle`: Toggle map in mapcycle (helper+)
- `DELETE /maps/{filename}`: Delete map and remove from mapcycles (helper+)
- `GET /login`, `GET /login/callback`, `GET|POST /logout`
