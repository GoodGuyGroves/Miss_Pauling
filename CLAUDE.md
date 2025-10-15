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
# Initialize database
python setup_database.py
```

## Architecture Overview

### Website Service Architecture
- **Authentication**: Discord OAuth (primary) + optional Steam account linking
- **Database**: SQLite with SQLAlchemy 2.0+ ORM, Alembic migrations
- **Templates**: Server-side Jinja2 rendering with TailwindCSS
- **Sessions**: HTTP-only cookie-based with CSRF protection
- **Key principle**: Discord is required auth, Steam is optional linkable

### FastDL Service Architecture  
- **File serving**: TF2 map files via `/tf/maps/{filename}` endpoints
- **Mapcycle management**: Toggle maps in/out of server mapcycle rotations
- **Multi-server support**: Manages multiple TF2 server instances
- **Configuration**: Centralized in `settings.json`

### Shared Database Schema
Located in `shared/models.py`:
- **Users**: Discord ID (required), Steam IDs (optional), profile data
- **UserSessions**: Active login sessions with expiration

## Service-Specific Notes

### Website Service (`website/`)
- **Entry point**: `app/main.py` 
- **Config**: `app/core/config.py` loads from `settings.json`
- **Auth flow**: `app/routers/auth.py` + `app/services/auth_service.py`
- **Templates**: Use TailwindCSS classes, minimal vanilla JavaScript
- **Steam integration**: Always use `steam_id64` as primary identifier

### FastDL Service (`fastdl/`)
- **Entry point**: `main.py`
- **Map management**: `core/mapcycle.py` handles state persistence
- **File uploads**: Size validation and extension checking
- **API endpoints**: RESTful design for map operations

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

### Security Considerations
- Configuration files with secrets (`settings.json`) are not committed
    - Prefer non-sensitive values in `settings.json` and sensitive values in `.env`
- HTTP-only secure cookies prevent XSS
- CSRF tokens on all forms
- Session-based auth with proper expiration

### File Structure
```
Miss_Pauling/
├── website/          # Web application with auth
├── fastdl/          # Map file server
├── docs/            # MkDocs documentation
├── shared/          # Common database models
└── requirements.txt # Root dependencies
```