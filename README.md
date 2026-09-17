# Miss Pauling

The pugs.tf website (Discord/Steam auth, user profiles, admin dashboard) and the
FastDL map server for the pug TF2 servers. Both run in **one process** from one
container image: requests for the FastDL hostname are routed to the FastDL
sub-application, everything else is the website.

See `CLAUDE.md` for the codebase layout. This file is the deployment guide.

Tests: `python -m pytest` from the repo root (pytest is in the dev section of `requirements.txt`). The suite is black-box over HTTP and is the reference for expected behaviour.

## Running locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# create `.env` at the repo root with the secrets listed under "Environment variables" below
uvicorn pauling.main:app --host 0.0.0.0 --port 8000 --reload
```

- Website: http://localhost:8000/
- FastDL: http://fastdl.localhost:8000/ (`fastdl.localhost` is in `pauling/fastdl/settings.json` `hosts`)
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

## Deploying to Kubernetes (the homelab cluster)

The target is the Argo CD cluster defined in the `homelab` repo
(`git@github.com:GoodGuyGroves/homelab.git`). Everything below follows that
repo's conventions; read its `gitops/README.md` if anything here looks stale.

### Facts about the cluster that shape this deployment

- **Argo CD, app-of-apps.** User workloads are auto-discovered: any directory
  `gitops/workloads/<name>/` with a `kustomization.yaml` becomes an Application
  named `<name>` in namespace `<name>`. No registration file is needed. Push to
  `main` and Argo CD syncs (webhook, else polling).
- **Plain Kustomize**, no Helm for our own apps, no ConfigMaps-from-files;
  config is `env:` on the Deployment.
- **Secrets are SOPS + age**, decrypted in-cluster by KSOPS. Files are
  `<x>.sops.yaml` (committed) and `<x>.dec.yaml` (gitignored), wired in through a
  `secret-generator.yaml` under `generators:` in the kustomization.
- **Ingress is Traefik** with `ingressClassName: traefik-public` (not the
  default class, so it must be set). Every Ingress carries the two
  `external-dns.alpha.kubernetes.io/*` annotations; external-dns then creates
  the Cloudflare records (`pugs.tf` is already in its domain filter). Traefik
  sets `X-Forwarded-Proto` itself; uvicorn trusts it via `--proxy-headers`.
- **TLS is cert-manager** with the `letsencrypt-prod` ClusterIssuer using
  DNS-01 through Cloudflare, so certificates issue before DNS resolves.
- **Storage**: omit `storageClassName` to get the default `local-path` class
  (ReadWriteOnce, node-local). Deployments owning such a volume use
  `strategy: Recreate`.
- **Nodes are arm64** (Talos on Apple Silicon). The image MUST have a
  `linux/arm64` manifest. Nothing is built in the homelab repo.
- **No image pull secrets** are configured; images come from public registries.

### Step 1: publish the image

`.github/workflows/build-image.yml` in this repo builds a multi-arch
(`linux/amd64,linux/arm64`) image on every push to `main` and pushes it to
`ghcr.io/goodguygroves/miss-pauling` with tags `latest` and `sha-<short sha>`.

One-time setup: after the first workflow run, open the package on GitHub
(Packages, miss-pauling, Package settings) and set its visibility to **public**,
because the cluster has no registry credentials.

### Step 2: copy the manifests into the homelab repo

Ready-made manifests live in `deploy/homelab/` here. Copy the directory:

```bash
cp -r deploy/homelab /path/to/homelab/gitops/workloads/miss-pauling
```

The directory name matters: it becomes the Application name and the namespace.

| File | What it is |
|---|---|
| `kustomization.yaml` | namespace `miss-pauling`; lists the resources; `generators: [secret-generator.yaml]` |
| `pvc.yaml` | `miss-pauling-data`, RWO, default class, mounted at `/data` |
| `deployment.yaml` | 1 replica, `Recreate`, `fsGroup: 10001`, env from the secret, probes on `/healthz` |
| `service.yaml` | ClusterIP on port 8000 |
| `certificate.yaml` | `miss-pauling-tls` for `pugs.tf`, `www.pugs.tf`, `fastdl.pugs.tf` |
| `ingress.yaml` | one Ingress, three hosts, all to the same Service, external-dns annotations |
| `secret-generator.yaml` | KSOPS generator pointing at `secrets.sops.yaml` |
| `secrets.dec.example.yaml` | template for the plaintext secret; never commit a filled-in copy |

Then pin the image tag in `deployment.yaml` to a `sha-…` tag from the workflow
run instead of `latest`.

### Step 3: create the secret

```bash
cd /path/to/homelab
cp gitops/workloads/miss-pauling/secrets.dec.example.yaml gitops/workloads/miss-pauling/secrets.dec.yaml
# fill in the values (Discord app secrets, Steam key, RCON passwords, a long random API secret key)
sops --encrypt gitops/workloads/miss-pauling/secrets.dec.yaml > gitops/workloads/miss-pauling/secrets.sops.yaml
rm gitops/workloads/miss-pauling/secrets.dec.example.yaml
```

The homelab `.sops.yaml` rule matches `gitops/**/*.sops.yaml` and encrypts only
`data`/`stringData`, so the file stays readable in review. `direnv` in that repo
provides `sops` and the age key.

### Step 4: commit, push, verify

```bash
git add gitops/workloads/miss-pauling && git commit -m "Add miss-pauling" && git push
argocd app get miss-pauling            # or watch it in the Argo CD UI
kubectl -n miss-pauling get pods,pvc,certificate,ingress
kubectl -n miss-pauling logs deploy/miss-pauling
curl -s https://www.pugs.tf/healthz    # {"status":"ok"}
curl -s https://fastdl.pugs.tf/tf/cfg/mapcycle_pt_all.txt
```

### Things not to do

- **Do not add the oauth2-proxy middleware annotations** to the Ingress. The
  site has its own Discord login, and `fastdl.pugs.tf` must stay anonymous so
  game clients can download maps.
- **Do not scale above one replica.** State is SQLite plus JSON on an RWO volume.
- **Do not put `settings.json` in a ConfigMap** unless you need to change
  non-secret config; the committed file is baked into the image and is correct
  for production. If you do, mount it and point `MISS_PAULING_SETTINGS_FILE`
  at the mount.

### Cutting over from the old VPS

1. Copy `db/sqlite.db` and the maps directory from the old host into the PVC
   (`kubectl cp` into the running pod at `/data/sqlite.db` and `/data/maps/`,
   then restart the pod). Skip this for a clean start; tables and roles are
   created on first boot.
2. Point the game servers' `sv_downloadurl` at `https://fastdl.pugs.tf/tf` and
   add a cron job that fetches `https://fastdl.pugs.tf/tf/cfg/mapcycle_<name>.txt`
   into each server's `tf/cfg/`.
3. Existing users will have to log in again because the cookie domain changed.

### Deployment checklist (summary)

1. **Single replica.** State is a SQLite file plus JSON files on one volume.
2. **One volume mounted at `/data`.** It holds the database (`/data/sqlite.db`),
   the FastDL map store (`/data/maps`) and mapcycle state (`/data/mapcycle.json`).
3. **Ingress: route all hostnames to the same Service.** The app decides which
   sub-application to serve from the `Host` header.
4. **Probes:** `GET /healthz` for liveness and readiness.
5. **`environment=production`** must be set (lowercase name). Without it cookies
   are sent without the `Secure` flag and the Discord login callback appends the
   session token to the FastDL return URL as a query parameter.
6. **Discord application:** the OAuth redirect URI stays
   `https://www.pugs.tf/auth/discord/callback`. Nothing to register for FastDL.

### Environment variables

| Variable | Required | Notes |
|---|---|---|
| `environment` | yes | Set to `production`. See item 5 above. |
| `MISS_PAULING_API_SECRET_KEY` | yes | Signing key for auth tokens. |
| `DISCORD_CLIENT_SECRET`, `DISCORD_TOKEN` | yes | Discord application secrets. |
| `STEAM_API_KEY` | yes | Steam Web API key for account linking. |
| `TF2_RCON_PASSWORD_<NAME>` | for the server browser | One per entry in `TF2_SERVERS`, name upper-cased with non-alphanumerics replaced by `_` (`TF2_RCON_PASSWORD_PUGA`, `TF2_RCON_PASSWORD_PUGB`). |
| `MISS_PAULING_COOKIE_DOMAIN` | no | Defaults to `.pugs.tf` from `settings.json`, which is what production needs so the login cookie is shared between `www` and `fastdl`. Set it to an empty string when testing on `localhost`, otherwise browsers reject the cookie. |
| `MISS_PAULING_DB_PATH` | no | SQLite file path. Defaults to `/data/sqlite.db` in the image. |
| `MISS_PAULING_DB_URL` | no | Full SQLAlchemy URL; overrides `MISS_PAULING_DB_PATH` (use for Postgres). |
| `MISS_PAULING_SETTINGS_FILE` | no | Path to the website's non-secret settings JSON. Defaults to the `settings.json` at the repo root, baked into the image; point at a ConfigMap mount to override. |
| `FASTDL_SETTINGS_FILE` | no | Same for `pauling/fastdl/settings.json`. |
| `FASTDL_ENABLED` | no | `false` to run the website without FastDL. |

### Non-secret configuration

`settings.json` and `pauling/fastdl/settings.json` are committed and baked into
the image. Override them with ConfigMaps via the `*_SETTINGS_FILE` variables above
rather than editing the image. Values in environment variables take precedence
over the JSON files.

`pauling/fastdl/settings.json` keys: `hosts` (hostnames routed to FastDL), `maps_dir`,
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
