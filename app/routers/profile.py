from fastapi import APIRouter
from app.core.config import settings
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request, Depends
from sqlalchemy.orm import Session
from app.db.database import get_db

# Configure templates and static files
templates = Jinja2Templates(directory="templates")

router = APIRouter(tags=["User profile"])

@router.get("/profile")
async def profile_page(request: Request, error: str = None, success: str = None, db: Session = Depends(get_db)):
    """Show user profile page"""
    from sqlalchemy.orm import Session
    from fastapi import Depends
    from app.core.sessions import get_current_user_from_session, generate_csrf_token, set_csrf_cookie
    
    # Get current user from session
    user = get_current_user_from_session(request, db)
    
    if not user:
        return RedirectResponse(url="/?error=Authentication required")
    
    # Generate CSRF token for forms
    csrf_token = generate_csrf_token()
    
    response = templates.TemplateResponse("profile.html", {
        "request": request,
        "user": user,
        "error": error,
        "success": success,
        "csrf_token": csrf_token
    })
    
    # Set CSRF token cookie
    set_csrf_cookie(response, csrf_token)
    
    return response