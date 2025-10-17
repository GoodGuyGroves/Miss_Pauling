from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional, List

from shared.database import get_db
from shared.repositories import UserRepository
from website.app.models.responses import UserValidationResponse
from website.app.services.tf2_service import tf2_service, ServerStatus
from website.app.services.logs_service import logs_service, GameLog

router = APIRouter(prefix="/api", tags=["API"])

security = HTTPBearer()

@router.post("/validate/token", response_model=UserValidationResponse)
async def validate_token(
    request: Request,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Validate a user session token and return user information.
    Used by other services (like FastDL) to validate authentication.
    """
    try:
        session_token = credentials.credentials
        
        # Get session from database
        session = UserRepository.get_session(db, session_token)
        if not session:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        
        # Get user information
        user = UserRepository.get_user_by_id(db, session.user_id)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        # Get user roles
        user_roles = UserRepository.get_user_roles(db, user.id)
        role_names = [role.name.value for role in user_roles]
        
        return UserValidationResponse(
            user_id=user.id,
            name=user.name,
            discord_id=user.discord_id,
            steam_id64=user.steam_id64,
            roles=role_names,
            is_authenticated=True
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Token validation failed: {str(e)}")

@router.get("/validate/session")
async def validate_session(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Validate a session cookie and return user information.
    Alternative endpoint for cookie-based validation.
    """
    try:
        session_token = request.cookies.get("session_token")
        if not session_token:
            raise HTTPException(status_code=401, detail="No session token provided")
        
        # Get session from database
        session = UserRepository.get_session(db, session_token)
        if not session:
            raise HTTPException(status_code=401, detail="Invalid or expired session")
        
        # Get user information
        user = UserRepository.get_user_by_id(db, session.user_id)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        # Get user roles
        user_roles = UserRepository.get_user_roles(db, user.id)
        role_names = [role.name.value for role in user_roles]
        
        return UserValidationResponse(
            user_id=user.id,
            name=user.name,
            discord_id=user.discord_id,
            steam_id64=user.steam_id64,
            roles=role_names,
            is_authenticated=True
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Session validation failed: {str(e)}")


@router.get("/servers", response_model=List[ServerStatus])
async def get_servers_status():
    """Get status of all configured TF2 servers"""
    try:
        servers = await tf2_service.get_all_servers_status()
        return servers
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to query servers: {str(e)}")


@router.get("/recent-games", response_model=List[GameLog])
async def get_recent_games():
    """Get recent games from logs.tf"""
    try:
        games = await logs_service.get_recent_games(limit=10)
        return games
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to query recent games: {str(e)}")