"""
Authentication for the FastDL sub-application.

FastDL runs inside the website process and shares its database, so sessions are
resolved directly with the website's session helpers rather than over HTTP.
"""
from typing import Optional, List
from fastapi import HTTPException, Request, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from pauling.db.database import get_db
from pauling.auth.sessions import get_current_user_from_session
from pauling.auth.roles import get_user_role_names, is_helper_or_above


class AuthenticatedUser(BaseModel):
    """User information exposed to FastDL routes and templates"""
    user_id: int
    name: Optional[str] = None
    discord_id: Optional[str] = None
    steam_id64: Optional[str] = None
    roles: List[str] = []
    is_authenticated: bool = True


async def get_current_user(request: Request, db: Session = Depends(get_db)) -> Optional[AuthenticatedUser]:
    """
    FastAPI dependency to get the current authenticated user.
    Returns None if not authenticated (doesn't raise an exception).
    """
    user = get_current_user_from_session(request, db)
    if not user:
        return None
    return AuthenticatedUser(
        user_id=user.id,
        name=user.name,
        discord_id=user.discord_id,
        steam_id64=user.steam_id64,
        roles=get_user_role_names(user, db),
    )


async def require_auth(request: Request, db: Session = Depends(get_db)) -> AuthenticatedUser:
    """
    FastAPI dependency that requires authentication.
    Raises 401 HTTPException if not authenticated.
    """
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


async def require_helper_or_above(request: Request, db: Session = Depends(get_db)) -> AuthenticatedUser:
    """
    FastAPI dependency that requires the helper role or above.
    Raises 403 HTTPException if the user has insufficient privileges.
    """
    user = get_current_user_from_session(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    if not is_helper_or_above(user, db):
        raise HTTPException(
            status_code=403,
            detail="Helper privileges or above required for this action"
        )

    return AuthenticatedUser(
        user_id=user.id,
        name=user.name,
        discord_id=user.discord_id,
        steam_id64=user.steam_id64,
        roles=get_user_role_names(user, db),
    )
