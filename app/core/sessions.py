from fastapi import Request, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
import secrets

from app.core.config import get_settings
from app.db.repositories import UserRepository
from app.db.database import get_db
from app.db.models import User

settings = get_settings()

def get_current_user_from_session(request: Request, db: Session) -> Optional[User]:
    """Get current user from session cookie"""
    session_token = request.cookies.get("session_token")
    if not session_token:
        return None
    
    try:
        # Get session from database
        session = UserRepository.get_session(db, session_token)
        if not session:
            return None
        
        # Get user
        user = UserRepository.get_user_by_id(db, session.user_id)
        return user
    except:
        return None

def create_session_cookie(response, session_token: str):
    """Set session cookie on response"""
    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        secure=True if settings.environment == "production" else False,
        samesite="lax",
        max_age=settings.MISS_PAULING_SESSION_EXPIRY_HOURS * 3600  # Convert hours to seconds
    )

def clear_session_cookie(response):
    """Clear session cookie"""
    response.delete_cookie(
        key="session_token",
        httponly=True,
        secure=True if settings.environment == "production" else False,
        samesite="lax"
    )

def generate_csrf_token() -> str:
    """Generate a CSRF token"""
    return secrets.token_urlsafe(32)

def validate_csrf_token(request: Request, form_token: str) -> bool:
    """Validate CSRF token from form against session"""
    session_csrf = request.cookies.get("csrf_token")
    return session_csrf and session_csrf == form_token

def set_csrf_cookie(response, csrf_token: str):
    """Set CSRF token cookie"""
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,  # JavaScript needs to read this for forms
        secure=True if settings.environment == "production" else False,
        samesite="lax",
        max_age=settings.MISS_PAULING_SESSION_EXPIRY_HOURS * 3600
    )