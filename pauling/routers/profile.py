from fastapi import APIRouter
from pauling.config import settings, TEMPLATES_DIR
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request, Depends
from sqlalchemy.orm import Session
from pauling.db.database import get_db

# Configure templates and static files
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(tags=["User profile"])

@router.get("/profile")
async def profile_page(request: Request, error: str = None, success: str = None, db: Session = Depends(get_db)):
    """Show user profile page"""
    from sqlalchemy.orm import Session
    from fastapi import Depends
    from pauling.auth.sessions import get_current_user_from_session, generate_csrf_token, set_csrf_cookie
    
    # Get current user from session
    user = get_current_user_from_session(request, db)
    
    if not user:
        return RedirectResponse(url="/?error=Authentication required")
    
    # Check if user has admin privileges
    from pauling.auth.roles import get_highest_role
    from pauling.models.admin import get_role_hierarchy
    
    highest_role = get_highest_role(user, db)
    is_admin = False
    if highest_role:
        is_admin = get_role_hierarchy(highest_role) <= 2  # moderator or above
    
    # Generate CSRF token for forms
    csrf_token = generate_csrf_token()
    
    response = templates.TemplateResponse(request, "profile.html", {
        "request": request,
        "user": user,
        "error": error,
        "success": success,
        "csrf_token": csrf_token,
        "is_admin": is_admin
    })
    
    # Set CSRF token cookie
    set_csrf_cookie(response, csrf_token)
    
    return response