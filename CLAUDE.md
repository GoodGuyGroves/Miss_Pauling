# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Miss Pauling is a multi-service Python application for Team Fortress 2 communities consisting of:

1. **Website Service** (`website/`): FastAPI web application with Discord/Steam authentication and user profiles
2. **FastDL Sub-application** (`fastdl/`): FastAPI sub-app for TF2 map distribution and mapcycle management, mounted inside the website process and served by hostname (`fastdl.pugs.tf`)
3. **Documentation** (`docs/`): MkDocs-based documentation site for user guides
4. **Shared Components** (`shared/`): Common database models and utilities

## Common Development Commands

### Environment Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Running Services
```bash
# Website + FastDL (single process, port 8000). Run from the repo root; no cwd assumptions.
uvicorn website.app.main:app --host 0.0.0.0 --port 8000 --reload
# FastDL is served on the hosts listed in fastdl/settings.json, e.g. http://fastdl.localhost:8000/

# Documentation site, served via website at /docs when docs/site exists (mkdocs is in the root requirements)
cd docs && mkdocs build

# Container image (what Kubernetes runs)
docker build -t miss-pauling . && docker run -p 8000:8000 -v pauling-data:/data miss-pauling
```

### Deployment (Kubernetes)
**Read `README.md` before deploying.** It has the checklist, the full environment variable table and the cross-host login flow. Summary:
- Set `environment=production` on the pod (lowercase). Otherwise cookies lack `Secure` and the Discord callback leaks the session token into the FastDL return URL
- One image (`Dockerfile`) runs website + FastDL with uvicorn behind the ingress; `--proxy-headers` is enabled so `X-Forwarded-Proto` is honoured
- Probe endpoint: `GET /healthz` (checks the database connection)
- Environment variables: secrets (`MISS_PAULING_API_SECRET_KEY`, `STEAM_API_KEY`, `DISCORD_CLIENT_SECRET`, `DISCORD_TOKEN`), `MISS_PAULING_DB_URL` or `MISS_PAULING_DB_PATH` (default `/data/sqlite.db` in the image), `MISS_PAULING_SETTINGS_FILE` and `FASTDL_SETTINGS_FILE` to point at ConfigMap mounts, `FASTDL_ENABLED`
- Persistent state lives on one volume mounted at `/data`: the SQLite file, FastDL's map store (`maps_dir`, default `/data/maps`) and mapcycle state (`/data/mapcycle.json`)
- Single replica: state is SQLite plus JSON files on that volume
- TF2 server RCON passwords come from `TF2_RCON_PASSWORD_<NAME>` env vars (e.g. `TF2_RCON_PASSWORD_PUGA`), one per entry in `TF2_SERVERS`
- The image is a two-stage build: mkdocs and the docs toolchain only exist in the builder stage; the runtime installs the section of `requirements.txt` above the `docs build only` marker
- No log viewing or service control in the admin UI: the website runs separately from the game servers, so use `kubectl logs` and cluster tooling

### Database Operations (Website Service)
```bash
cd website
# Create migration
alembic revision --autogenerate -m "description"
# Apply migrations
alembic upgrade head
# Database is automatically initialized when the website starts
```

## Architecture Overview

### Website Service Architecture
- **Authentication**: Discord OAuth (primary) + optional Steam account linking
- **Authorization**: Role-Based Access Control (RBAC) with 6 roles: superadmin, administrator, moderator, helper, captain, user
- **Database**: SQLite with SQLAlchemy 2.0+ ORM, auto-initialization on startup
- **Templates**: Server-side Jinja2 rendering with TailwindCSS
- **Sessions**: HTTP-only cookie-based with CSRF protection
- **Server Browser**: Live TF2 server monitoring via RCON (credentials from config/env, not the game server's files)
- **Game History**: Recent match logs integration with logs.tf API
- **Key principle**: Discord is required auth, Steam is optional linkable

### FastDL Architecture
- **Deployment**: Not a separate process. `website/app/main.py` mounts `fastdl.app:app` with Starlette `Host` routes for the hostnames in `fastdl/settings.json`; all other hosts fall through to the website. Disable with `FASTDL_ENABLED: false`.
- **Standalone map store**: maps live in `maps_dir` on the FastDL volume; nothing is read from or written to a game server's filesystem
- **File serving**: TF2 map files via `/tf/maps/{filename}` endpoints
- **Mapcycle management**: Toggle maps in/out of named mapcycles (requires helper+ privileges); servers download the result from `/tf/cfg/mapcycle_{name}.txt`
- **Map deletion**: Delete map files (requires helper+ privileges)
- **Configuration**: `fastdl/settings.json` (loaded relative to the package, not the cwd)
- **Auth**: Uses the website's session and role helpers directly against the shared database. The session cookie is shared across subdomains via `MISS_PAULING_COOKIE_DOMAIN` (set to `.pugs.tf` in production).

### Shared Database Schema
Located in `shared/models.py`:
- **Users**: Discord ID (required), Steam IDs (optional), profile data
- **UserSessions**: Active login sessions with expiration
- **Roles**: Available user roles (superadmin, administrator, moderator, helper, captain, user)
- **UserRoles**: Many-to-many junction table for user-role assignments

## Service-Specific Notes

### Website Service (`website/`)
- **Entry point**: `app/main.py` (auto-creates database tables and default roles)
- **Config**: `app/core/config.py` loads from `settings.json`
- **Auth flow**: `app/routers/auth.py` + `app/services/auth_service.py`
- **Role system**: `app/core/roles.py` provides decorators and utilities for RBAC
- **Admin dashboard**: `app/routers/admin.py` provides `/admin` and `/admin/users`
- **TF2 Integration**: `app/services/tf2_service.py` handles RCON queries for live server data
- **Game Logs**: `app/services/logs_service.py` integrates with logs.tf API for match history
- **Templates**: Use TailwindCSS classes, minimal vanilla JavaScript
- **Steam integration**: Always use `steam_id64` as primary identifier
- **Navigation**: Conditional UI elements based on user roles (`is_admin` template variable)

### FastDL (`fastdl/`)
- **Entry point**: `app.py` (sub-application, mounted by the website)
- **Map management**: `core/mapcycle.py` persists mapcycle membership in `mapcycle_state_file` and renders `mapcycle_{name}.txt` on request
- **File uploads**: Size validation and extension checking
- **API endpoints**: RESTful design for map operations
- **Role enforcement**: `core/auth.py` provides `require_helper_or_above()` dependency built on `website/app/core/roles.py`

### Documentation (`docs/`)
- **Build**: `mkdocs build` (outputs to `site/`)
- **Content**: Markdown files in `content/` directory
- **Theme**: Material Design theme

## Development Patterns

### SQLAlchemy 2.0+ Modern Patterns
- Use `Mapped` type annotations with `mapped_column()`
- `DeclarativeBase` instead of legacy `declarative_base()`
- Modern `select()` syntax instead of `query()` methods
- `datetime.now(timezone.utc)` instead of deprecated `utcnow()`

### Role-Based Access Control (RBAC)
- **Repository methods**: Use `UserRepository` for role management (`assign_role`, `user_has_role`, etc.)
- **Route protection**: Use `@require_roles(["admin"])` decorator to protect endpoints
- **Permission checks**: Use helper functions like `is_admin(user, db)` or `is_moderator_or_above(user, db)`
- **Auto-assignment**: New users automatically get "user" role on account creation
- **Role hierarchy**: superadmin (0) > administrator (1) > moderator (2) > helper (3) > captain (4) > user (5)
- **Admin dashboard**: Access at `/admin` (moderator+ required), user management at `/admin/users`
- **Role assignment rules**: Users can only assign roles lower in hierarchy than their own highest role
- **Audit logging**: Role changes are logged to console with format: `ROLE ASSIGNED/REMOVED: User [Admin] assigned/removed 'role' to/from user [Target]`
- **FastDL integration**: FastDL enforces helper+ for map deletion and mapcycle operations using the same role helpers
- **UI integration**: Admin links only visible to moderator+, conditional navigation elements

### Security Considerations
- Configuration files with secrets (`settings.json`) are not committed
    - Prefer non-sensitive values in `settings.json` and sensitive values in `.env`
- HTTP-only secure cookies prevent XSS
- CSRF tokens on all forms
- Session-based auth with proper expiration

## Admin Management

### Admin Dashboard Web Interface
- **Main dashboard**: `/admin` - Overview and navigation (moderator+ required)
- **User management**: `/admin/users` - List users, assign/remove roles with checkboxes
- **Real-time updates**: AJAX role assignment without page refresh
- **Not included**: log viewing or service control. The website runs in Kubernetes, separate from the game servers; use `kubectl logs` and the cluster tooling instead
- **Role restrictions**: Can only assign roles lower than own highest role
- **Self-protection**: Cannot modify own roles via dashboard


### Command Line Admin Tools
```bash
# List all users
python admin_roles.py list-users

# Show user's current roles  
python admin_roles.py user-roles <user_id>

# Assign role to user
python admin_roles.py assign <user_id> <role_name>

# Remove role from user
python admin_roles.py remove <user_id> <role_name>

# Search for users
python admin_roles.py find-user <search_term>
```

### API Endpoints
- **Session validation**: `/api/validate/session` - Returns user info including roles (for external clients; FastDL no longer uses it)
- **Role assignment**: `POST /admin/users/assign-role` - Assign/remove roles (CSRF protected)
- **User data**: `GET /admin/users/data` - Get users list for AJAX updates
- **Server status**: `GET /api/servers` - Live TF2 server data via RCON
- **Recent games**: `GET /api/recent-games` - Last 10 games from logs.tf

### File Structure
```
Miss_Pauling/
├── website/          # Web application with auth
│   ├── app/routers/admin.py     # Admin dashboard routes (includes logs WebSocket)
│   ├── app/models/admin.py      # Admin Pydantic models
│   ├── app/services/tf2_service.py    # TF2 RCON integration
│   ├── app/services/logs_service.py   # logs.tf API integration
│   ├── app/core/roles.py        # RBAC decorators and utilities
│   ├── app/core/config.py       # Settings including TF2_SERVERS and LOGS_TF_UPLOADER_STEAM_ID
│   └── templates/admin/         # Admin dashboard templates (dashboard, users)
├── fastdl/          # FastDL sub-app, host-routed from the website process
│   ├── app.py                  # FastDL FastAPI sub-application
│   └── core/auth.py            # Role enforcement for FastDL
├── docs/            # MkDocs documentation
├── shared/          # Common database models
├── admin_roles.py   # CLI admin tool
├── .github/dependabot.yml   # Grouped weekly dependency PRs
└── requirements.txt # Single dependency file for website, FastDL and docs
```