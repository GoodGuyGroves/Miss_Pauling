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
from website.app.routers import auth, profile, api, admin
from shared.database import engine, Base, get_db
from shared.models import User, Role, UserRole, RoleType
from website.app.models.auth import UserInfo
from website.app.models.responses import HomePageContext

# Initialize database tables and default data
# Comment this out if using Alembic for migrations
Base.metadata.create_all(bind=engine)

# Create default roles if they don't exist
from sqlalchemy.orm import sessionmaker
Session = sessionmaker(bind=engine)
with Session() as session:
    existing_roles = session.query(Role).count()
    if existing_roles == 0:
        print("Creating default roles...")
        default_roles = [
            Role(name=RoleType.SUPERADMIN, description="Super Administrator with full system access"),
            Role(name=RoleType.ADMINISTRATOR, description="Administrator with system management access"),
            Role(name=RoleType.MODERATOR, description="Moderator with content management access"),
            Role(name=RoleType.HELPER, description="Helper with limited support access"),
            Role(name=RoleType.CAPTAIN, description="Team captain with team management access"),
            Role(name=RoleType.USER, description="Standard user with basic access"),
        ]
        
        for role in default_roles:
            session.add(role)
        
        session.commit()
        print(f"Created {len(default_roles)} default roles")

# Create FastAPI application instance
app = FastAPI(
    title="pugs.tf",
    description="A TF2 community platform with Steam and Discord authentication",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# Configure templates and static files
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Add mkdocs to /docs
docs_path = Path(__file__).parent.parent.parent / "docs" / "site"
app.mount("/docs", StaticFiles(directory=str(docs_path), html=True), name="docs")

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
    from website.app.core.roles import get_highest_role
    from website.app.models.admin import get_role_hierarchy
    
    user_db: User | None = get_current_user_from_session(request, db)
    
    # Convert SQLAlchemy user to Pydantic model if the user exists
    user_info = None
    is_admin = False
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
        
        # Check if user has admin privileges (moderator or above)
        highest_role = get_highest_role(user_db, db)
        if highest_role:
            is_admin = get_role_hierarchy(highest_role) <= 2  # moderator or above
    
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
        "is_admin": is_admin,
        **context.model_dump()
    })
    
    set_csrf_cookie(response, csrf_token)
    
    return response

app.include_router(profile.router)
app.include_router(auth.router)
app.include_router(api.router)
app.include_router(admin.router)
