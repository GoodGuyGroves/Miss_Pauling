# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Miss Pauling is a multi-service Python application for Team Fortress 2 communities consisting of:

1. **Website Service** (`website/`): FastAPI web application with Discord/Steam authentication and user profiles
2. **FastDL Service** (`fastdl/`): FastAPI file server for TF2 map distribution and mapcycle management  
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
# Website service (port 8000)
cd website && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# FastDL service (port 8001)  
cd website && uvicorn main:app --host 0.0.0.0 --port 8001 --reload

# Documentation site, served via website
cd docs && mkdocs build
```

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
- **Key principle**: Discord is required auth, Steam is optional linkable

### FastDL Service Architecture  
- **File serving**: TF2 map files via `/tf/maps/{filename}` endpoints
- **Mapcycle management**: Toggle maps in/out of server mapcycle rotations (requires helper+ privileges)
- **Map deletion**: Delete map files (requires helper+ privileges)
- **Multi-server support**: Manages multiple TF2 server instances
- **Configuration**: Centralized in `settings.json`
- **Role integration**: Cross-service authentication with website for role-based permissions

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
- **Admin dashboard**: `app/routers/admin.py` provides `/admin`, `/admin/users`, and `/admin/logs` management interface
- **Templates**: Use TailwindCSS classes, minimal vanilla JavaScript
- **Steam integration**: Always use `steam_id64` as primary identifier
- **Navigation**: Conditional UI elements based on user roles (`is_admin` template variable)

### FastDL Service (`fastdl/`)
- **Entry point**: `main.py`
- **Map management**: `core/mapcycle.py` handles state persistence
- **File uploads**: Size validation and extension checking
- **API endpoints**: RESTful design for map operations
- **Role enforcement**: `core/auth.py` provides `require_helper_or_above()` dependency
- **Cross-service auth**: Validates sessions via website API `/api/validate/session`

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
- **Admin dashboard**: Access at `/admin` (moderator+ required), user management at `/admin/users`, server logs at `/admin/logs`
- **Role assignment rules**: Users can only assign roles lower in hierarchy than their own highest role
- **Audit logging**: Role changes are logged to console with format: `ROLE ASSIGNED/REMOVED: User [Admin] assigned/removed 'role' to/from user [Target]`
- **Cross-service integration**: FastDL service enforces helper+ for map deletion and mapcycle operations
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
- **Server logs**: `/admin/logs` - Real-time systemd service log monitoring with WebSocket streaming
- **Real-time updates**: AJAX role assignment without page refresh
- **Role restrictions**: Can only assign roles lower than own highest role
- **Self-protection**: Cannot modify own roles via dashboard

### Server Logs System
- **Configuration**: Systemd services configured in `settings.json` under `SYSTEMD_SERVICES`
- **Service format**: Each service requires `display_name`, `description`, and `journalctl_args` array
- **Real-time streaming**: WebSocket-based log streaming using `journalctl -f --output=json`
- **Service management**: Restart services directly from web interface with `systemctl restart`
- **Tab interface**: Browser-like tabs for switching between different services
- **Auto-scroll control**: "Watch" checkbox to enable/disable automatic scrolling
- **User access**: Moderator+ privileges required for log access and service restart
- **Audit logging**: All service restart actions are logged with user attribution

#### Example Service Configuration
```json
{
  "SYSTEMD_SERVICES": {
    "podman-newt": {
      "display_name": "Newt Service",
      "description": "Podman container for Newt service",
      "journalctl_args": ["--user", "-u", "podman-newt"]
    }
  }
}
```

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
- **Session validation**: `/api/validate/session` - Returns user info including roles
- **Role assignment**: `POST /admin/users/assign-role` - Assign/remove roles (CSRF protected)
- **User data**: `GET /admin/users/data` - Get users list for AJAX updates
- **Log streaming**: `WebSocket /admin/logs/stream/{service_name}` - Real-time systemd log streaming
- **Service restart**: `POST /admin/logs/restart/{service_name}` - Restart systemd services

### File Structure
```
Miss_Pauling/
├── website/          # Web application with auth
│   ├── app/routers/admin.py     # Admin dashboard routes (includes logs WebSocket)
│   ├── app/models/admin.py      # Admin Pydantic models
│   ├── app/core/roles.py        # RBAC decorators and utilities
│   ├── app/core/config.py       # Settings including SYSTEMD_SERVICES config
│   └── templates/admin/         # Admin dashboard templates (dashboard, users, logs)
├── fastdl/          # Map file server
│   └── core/auth.py            # Role enforcement for FastDL
├── docs/            # MkDocs documentation
├── shared/          # Common database models
├── admin_roles.py   # CLI admin tool
└── requirements.txt # Root dependencies
```