# Miss Pauling

The pugs.tf website (Discord/Steam auth, user profiles, admin dashboard) and the
FastDL map server for the pug TF2 servers. Both run in **one process** from one
container image: requests for the FastDL hostname are routed to the FastDL
sub-application, everything else is the website.

See `CLAUDE.md` for the codebase layout. This file is the deployment guide.

## Running locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# create website/.env with the secrets listed under "Environment variables" below
uvicorn website.app.main:app --host 0.0.0.0 --port 8000 --reload
```

- Website: http://localhost:8000/
- FastDL: http://fastdl.localhost:8000/ (`fastdl.localhost` is in `fastdl/settings.json` `hosts`)
- Docs: http://localhost:8000/docs/ after `cd docs && mkdocs build`

Set `FASTDL_ENABLED=false` to run the website without FastDL.

## Container image

```bash
docker build -t miss-pauling .
docker run -p 8000:8000 -v miss-pauling-data:/data \
  -e MISS_PAULING_API_SECRET_KEY=... -e STEAM_API_KEY=... \
  -e DISCORD_CLIENT_SECRET=... -e DISCORD_TOKEN=... miss-pauling
```

Two-stage build on `python:3.13-alpine`. The builder installs everything in
`requirements.txt` and builds the docs site; the runtime stage installs only the
packages **above** the `# --- docs build only` marker in `requirements.txt`, so
keep that marker in place when editing dependencies. Runs as a non-root user.
Persistent state lives under `/data`.

## Deploying to Kubernetes

### Checklist

1. **Single replica.** State is a SQLite file plus JSON files on one volume.
2. **One volume mounted at `/data`.** It holds the database (`/data/sqlite.db`),
   the FastDL map store (`/data/maps`) and mapcycle state (`/data/mapcycle.json`).
3. **Ingress: route both hostnames to the same Service** (`www.pugs.tf` and
   `fastdl.pugs.tf`). The app decides which sub-application to serve from the
   `Host` header. The ingress must forward `X-Forwarded-Proto`; uvicorn is started
   with `--proxy-headers` so generated URLs use https.
4. **Probes:** `GET /healthz` for liveness and readiness. It runs a query against
   the database.
5. **Set the environment variables below.** In particular `environment=production`
   (lowercase name, the settings class is case-sensitive). Without it cookies are
   sent without the `Secure` flag and the Discord login callback appends the session
   token to the FastDL return URL as a query parameter, which is a development-only
   hand-off that leaks the token into logs and browser history.
6. **Discord application:** the OAuth redirect URI stays
   `https://www.pugs.tf/auth/discord/callback`. FastDL never talks to Discord;
   it redirects to the website to log in and the shared cookie brings the session
   back. Nothing to register for the FastDL hostname.
7. **Game servers** no longer share a filesystem with this app. Point
   `sv_downloadurl` at `https://fastdl.pugs.tf/tf` and download mapcycle files
   from `https://fastdl.pugs.tf/tf/cfg/mapcycle_<name>.txt` (e.g. with a cron job
   into each server's `tf/cfg/`).

### Environment variables

| Variable | Required | Notes |
|---|---|---|
| `environment` | yes | Set to `production`. See item 5 above. |
| `MISS_PAULING_API_SECRET_KEY` | yes | Signing key for auth tokens. |
| `DISCORD_CLIENT_SECRET`, `DISCORD_TOKEN` | yes | Discord application secrets. |
| `STEAM_API_KEY` | yes | Steam Web API key for account linking. |
| `TF2_RCON_PASSWORD_<NAME>` | for the server browser | One per entry in `TF2_SERVERS`, name upper-cased with non-alphanumerics replaced by `_` (`TF2_RCON_PASSWORD_PUGA`, `TF2_RCON_PASSWORD_PUGB`). |
| `MISS_PAULING_COOKIE_DOMAIN` | no | Defaults to `.pugs.tf` from `website/settings.json`, which is what production needs so the login cookie is shared between `www` and `fastdl`. Set it to an empty string when testing on `localhost`, otherwise browsers reject the cookie. |
| `MISS_PAULING_DB_PATH` | no | SQLite file path. Defaults to `/data/sqlite.db` in the image. |
| `MISS_PAULING_DB_URL` | no | Full SQLAlchemy URL; overrides `MISS_PAULING_DB_PATH` (use for Postgres). |
| `MISS_PAULING_SETTINGS_FILE` | no | Path to the website's non-secret settings JSON. Defaults to the `website/settings.json` baked into the image; point at a ConfigMap mount to override. |
| `FASTDL_SETTINGS_FILE` | no | Same for `fastdl/settings.json`. |
| `FASTDL_ENABLED` | no | `false` to run the website without FastDL. |

### Non-secret configuration

`website/settings.json` and `fastdl/settings.json` are committed and baked into
the image. Override them with ConfigMaps via the `*_SETTINGS_FILE` variables above
rather than editing the image. Values in environment variables take precedence
over the JSON files.

`fastdl/settings.json` keys: `hosts` (hostnames routed to FastDL), `maps_dir`,
`mapcycle_state_file`, `mapcycles`, `allowed_map_extensions`,
`max_map_file_size` (MB), `website_base_url` (where FastDL sends users to log in).

### How login works across the two hostnames

1. `fastdl.pugs.tf/login` redirects to `www.pugs.tf/auth/redirect-login` with the
   FastDL callback as `return_to`.
2. The website sends the user to Discord with `return_to` encoded in the OAuth state.
3. Discord returns to `www.pugs.tf/auth/discord/callback`, which creates the session,
   sets the `session_token` cookie with `Domain=.pugs.tf`, and redirects to FastDL.
4. FastDL reads the same cookie and looks the session up in the shared database.
   Logging out on either host invalidates the session for both.

### What is deliberately not here

- No systemd units, `journalctl` log viewer or service-restart buttons. The app
  runs separately from the game servers now; use `kubectl logs`.
- No RCON password parsing from `server.cfg`; passwords come from env vars.
- No writing of mapcycle files into game server directories; they are served
  over HTTP instead.
