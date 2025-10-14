from itsdangerous import URLSafeSerializer, BadSignature
from fastapi import HTTPException, Depends
from sqlalchemy.orm import Session
from typing import Optional

from website.app.core.config import settings
from shared.repositories import UserRepository
from shared.database import get_db
# from website.app.schemas import UserInfo
from website.app.models.auth import UserInfo

# Create serializer for signing data
serializer = URLSafeSerializer(settings.MISS_PAULING_API_SECRET_KEY.get_secret_value())

def create_token(user_data: dict, session_token: str) -> str:
    """Create a signed token with user info and session token"""
    token_data = {
        "user": user_data,
        "session_token": session_token
    }
    return serializer.dumps(token_data)

def verify_token(token: str) -> dict:
    """Verify the authentication token and return data"""
    try:
        return serializer.loads(token)
    except BadSignature:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

def get_current_user(
    token: str, 
    db: Session = Depends(get_db)
) -> UserInfo:
    """Get the current authenticated user"""
    try:
        # Load token data
        token_data = verify_token(token)
        
        if not isinstance(token_data, dict) or "session_token" not in token_data:
            raise HTTPException(status_code=401, detail="Invalid authentication token format")
            
        # Verify the session is still valid
        session = UserRepository.get_session(db, token_data["session_token"])
        if not session:
            raise HTTPException(status_code=401, detail="Session expired or invalid")
            
        # Get the user
        user = UserRepository.get_user_by_id(db, session.user_id)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
            
        return user
    except BadSignature:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

def user_to_response(user, session_provider: Optional[str] = None) -> UserInfo:
    """Convert database User to response UserInfo model"""
    providers = []
    
    if user.steam_id64:
        providers.append({
            "provider": "steam", 
            "provider_id": user.steam_id64, 
            "linked": True
        })
    
    if user.discord_id:
        providers.append({
            "provider": "discord", 
            "provider_id": user.discord_id, 
            "linked": True
        })
    
    return UserInfo(
        id=user.id,
        steam_id64=user.steam_id64,
        steam_id=user.steam_id,
        steam_id3=user.steam_id3,
        steam_profile_url=user.steam_profile_url,
        discord_id=user.discord_id,
        name=user.name,
        avatar=str(user.avatar_url) if user.avatar_url else None,
        auth_providers=providers
    )