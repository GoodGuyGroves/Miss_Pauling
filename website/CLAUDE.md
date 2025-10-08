# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Development Commands

### Backend (FastAPI + SQLAlchemy + Jinja2 Templates)
- **Start development server**: `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`
- **Database migrations**: 
  - Create migration: `alembic revision --autogenerate -m "description"`
  - Apply migrations: `alembic upgrade head`
- **Initialize database**: `python setup_database.py`

## Architecture Overview

### Application Structure
This is a server-side rendered web application called "Miss Pauling" that supports Discord and Steam login with account linking capabilities.

**Key Design Principles:**
- Discord is the primary authentication method (required, cannot be unlinked)
- Steam accounts can be linked/unlinked to Discord accounts
- Users cannot log in directly with Steam - only through account linking
- All Steam ID formats are tracked (SteamID, SteamID3, SteamID64)
- Server-side rendered HTML with minimal client-side JavaScript

### Backend Architecture (FastAPI + Jinja2)
- **Entry point**: `app/main.py` - FastAPI application with template rendering
- **Templates**: `templates/` - Jinja2 HTML templates with TailwindCSS
- **Static files**: `static/` - CSS and JavaScript assets
- **Database**: SQLite with SQLAlchemy 2.0+ ORM, Alembic migrations
- **Models**: `app/db/models.py` - User and UserSession tables with `Mapped` type annotations
- **Authentication**: 
  - `app/api/web_auth.py` - Web-based auth endpoints (forms, cookies)
  - `app/api/auth.py` - Legacy API endpoints (kept for compatibility)
  - `app/services/auth_service.py` - Authentication business logic
  - `app/core/sessions.py` - Session and cookie management
  - `app/core/security.py` - Token creation and validation
- **Configuration**: `app/config.json` - Runtime configuration (not committed with secrets)
- **Steam Integration**: `app/core/steam_utils.py` - Steam API utilities

### Frontend Architecture (Server-Side Templates)
- **Templates**: Jinja2 templates with TailwindCSS styling
- **Base template**: `templates/base.html` - Common layout and navigation
- **Pages**: `templates/home.html`, `templates/profile.html`
- **JavaScript**: Minimal vanilla JS in `static/js/app.js` for basic interactions
- **Styling**: TailwindCSS via CDN for consistent UI components

### Database Schema
- **Users table**: Stores user profiles with multiple authentication providers
  - `discord_id` (required, unique) - Primary authentication
  - `steam_id64`, `steam_id`, `steam_id3` (optional) - Steam account formats
  - Profile data: `name`, `avatar_url`
- **UserSessions table**: Active login sessions with expiration

### Authentication Flow
1. **Discord Login**: Primary authentication method via OAuth2
2. **Steam Linking**: Optional, post-login account linking via OpenID
3. **Session Management**: HTTP-only cookie-based sessions with CSRF protection
4. **Form Security**: All forms include CSRF tokens for security
5. **Force Linking**: Admin capability to transfer Steam accounts between users

## Development Setup

### Configuration Files
- Backend config: `app/config.json` (create from template, never commit with real secrets)


### Key Dependencies
- **Backend**: FastAPI, SQLAlchemy 2.0+, Alembic, Jinja2, python-multipart, itsdangerous, python-jose, httpx, python3-openid

## Important Implementation Notes

### SQLAlchemy 2.0+ Modern Patterns
- **Models**: Use `Mapped` type annotations with `mapped_column()` for full type safety
- **Base Class**: `DeclarativeBase` instead of legacy `declarative_base()`
- **Queries**: Modern `select()` syntax instead of legacy `query()` methods
- **Session Management**: Context manager pattern with `Session(engine)` 
- **Timezone Awareness**: `datetime.now(timezone.utc)` instead of deprecated `utcnow()`

### Session Management
- HTTP-only cookies for secure session storage
- CSRF tokens required for all form submissions
- Session tokens stored in database with expiration
- Automatic session cleanup on logout

### Steam ID Handling
- Always use `steam_id64` as the primary identifier for Steam accounts
- Store all three formats (`steam_id`, `steam_id3`, `steam_id64`) for compatibility
- Steam linking requires fetching user data from Steam Web API

### Security Considerations
- Discord OAuth secrets and Steam API keys stored in `config.json`
- HTTP-only secure cookies prevent XSS attacks
- CSRF tokens protect against cross-site request forgery
- Session-based authentication with proper expiration

### Account Management
- Users cannot unlink Discord (primary auth method)
- Steam accounts can be forcibly transferred between users
- Unlinking the last auth method triggers automatic logout

### Template System
- Jinja2 templates for server-side rendering
- TailwindCSS for consistent styling
- Minimal vanilla JavaScript for essential interactions (copy to clipboard, form validation)
- No client-side frameworks or complex JavaScript dependencies