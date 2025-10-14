import sys
from pathlib import Path
# Add the repository root to Python path so we can import website and shared modules
sys.path.append(str(Path(__file__).parent.parent.parent))

from typing import Annotated, Optional
from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from website.app.core.config import settings
from website.app.routers import auth, profile, api
from shared.database import engine, Base, get_db
from shared.models import User
from website.app.models.auth import UserInfo
from website.app.models.responses import HomePageContext

# Initialize database tables
# Comment this out if using Alembic for migrations
Base.metadata.create_all(bind=engine)

# Create FastAPI application instance
app = FastAPI(
    title="Miss Pauling",
    description="A minimal FastAPI application with Steam and Discord authentication",
    version="0.1.0"
)

# Configure templates and static files
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Add CORS middleware to allow requests from the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.MISS_PAULING_CORS_ORIGINS,
    allow_credentials=settings.MISS_PAULING_CORS_CREDENTIALS,
    allow_methods=settings.MISS_PAULING_CORS_METHODS,
    allow_headers=settings.MISS_PAULING_CORS_HEADERS
)


@app.get("/", response_class=HTMLResponse)
@app.post("/", response_class=HTMLResponse)
async def root(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    error: Optional[str] = None,
    success: Optional[str] = None
) -> HTMLResponse:
    """Show home page with login or user dashboard"""
    from website.app.core.sessions import get_current_user_from_session, generate_csrf_token, set_csrf_cookie
    
    user_db: User | None = get_current_user_from_session(request, db)
    
    # Convert SQLAlchemy user to Pydantic model if the user exists
    user_info = None
    if user_db:
        user_info = UserInfo.model_validate({
            "id": user_db.id,
            "steam_id64": user_db.steam_id64,
            "steam_id": user_db.steam_id,
            "steam_id3": user_db.steam_id3,
            "steam_profile_url": user_db.steam_profile_url,
            "discord_id": user_db.discord_id,
            "name": user_db.name,
            "avatar": user_db.avatar_url,
            "auth_providers": []
        })
    
    csrf_token = generate_csrf_token()
    
    # Create validated context using Pydantic model
    context = HomePageContext(
        user=user_info,
        error=error,
        success=success,
        csrf_token=csrf_token
    )
    
    response = templates.TemplateResponse("home.html", {
        "request": request,
        **context.model_dump()
    })
    
    set_csrf_cookie(response, csrf_token)
    
    return response

app.include_router(profile.router)
app.include_router(auth.router)
app.include_router(api.router)
