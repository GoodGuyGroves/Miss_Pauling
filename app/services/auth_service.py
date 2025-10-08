import httpx
import re
from urllib.parse import quote_plus
from fastapi import HTTPException, Request
from sqlalchemy.orm import Session
from typing import Optional, Dict, Tuple

from app.db.models import User
from app.db.repositories import UserRepository, AuthProvider
from app.core.config import settings, get_default_headers
from app.core.security import serializer, create_token, user_to_response
from app.models.auth import UserInfo, OpenIDParams, DiscordTokenResponse, DiscordUserResponse, SteamUserData
from app.core.steam_utils import get_steam_user_data


async def validate_steam_auth(params: OpenIDParams) -> str:
    """Validate Steam OpenID authentication and return Steam ID"""
    # Validate the response by making a request back to Steam
    # Convert Pydantic model to validation parameters
    validation_params = params.model_dump(by_alias=True, exclude_none=True)
    validation_params["openid.mode"] = "check_authentication"
    
    # Get default headers
    headers = get_default_headers(settings)
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            str(settings.STEAM_OPENID_URL), 
            data=validation_params,
            headers=headers
        )
        if "is_valid:true" not in resp.text:
            raise HTTPException(status_code=401, detail="Steam authentication failed")
    
    # Extract the Steam ID from the claim
    if not params.claimed_id:
        raise HTTPException(status_code=401, detail="Missing Steam OpenID claimed_id")
    
    match = re.search(r"^https://steamcommunity.com/openid/id/(\d+)$", params.claimed_id)
    if not match:
        raise HTTPException(status_code=401, detail="Could not extract Steam ID")
    
    return match.group(1)

async def get_steam_user_info(steam_id64: str) -> SteamUserData:
    """Fetch user information from Steam API using the consolidated function"""
    # Use the consolidated function from steam_utils
    raw_data = await get_steam_user_data(steam_id64)
    
    # Validate and return as SteamUserData model
    try:
        return SteamUserData(**raw_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Invalid Steam API response: {str(e)}")

async def exchange_discord_code(code: str) -> DiscordUserResponse:
    """Exchange Discord OAuth2 code for access token and user data"""
    headers = get_default_headers(settings)
    
    # Exchange authorization code for access token
    token_data = {
        "client_id": settings.DISCORD_APPLICATION_ID,
        "client_secret": settings.DISCORD_CLIENT_SECRET.get_secret_value(),
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": str(settings.DISCORD_CALLBACK_URL),
    }
    
    token_headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        **headers
    }
    
    async with httpx.AsyncClient() as client:
        try:
            token_response = await client.post(
                str(settings.DISCORD_TOKEN_URL),
                data=token_data,
                headers=token_headers
            )
            
            if token_response.status_code != 200:
                error_detail = token_response.text
                
                if "invalid_client" in error_detail:
                    error_msg = (
                        "Discord authentication failed: Invalid client credentials. "
                        "Please verify your Discord client_id and client_secret in config.json "
                        "and ensure the redirect_uri exactly matches what's registered in the Discord Developer Portal."
                    )
                    raise HTTPException(status_code=500, detail=error_msg)
                
                raise HTTPException(status_code=401, detail=f"Failed to get Discord access token: {error_detail}")
            
            # Validate Discord token response
            try:
                discord_token = DiscordTokenResponse(**token_response.json())
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Invalid Discord token response: {str(e)}")
                
            access_token = discord_token.access_token
            
            # Get user information from Discord API
            user_response = await client.get(
                f"{str(settings.DISCORD_API_URL)}/users/@me",
                headers={"Authorization": f"Bearer {access_token}", **headers}
            )
            
            if user_response.status_code != 200:
                raise HTTPException(status_code=401, detail=f"Failed to get Discord user info: {user_response.text}")
            
            # Validate Discord user response
            try:
                return DiscordUserResponse(**user_response.json())
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Invalid Discord user response: {str(e)}")
        except Exception as e:
            if not isinstance(e, HTTPException):
                raise HTTPException(status_code=500, detail=f"Error during Discord authentication: {str(e)}")
            raise e

def process_discord_user_data(discord_user: DiscordUserResponse) -> Dict[str, Optional[str]]:
    """Process Discord user data into a standardized format"""
    discord_id = discord_user.id
    username = discord_user.username
    avatar_hash = discord_user.avatar
    
    # Construct avatar URL if available
    avatar_url = None
    if avatar_hash:
        avatar_format = "png"
        if avatar_hash.startswith("a_"):
            avatar_format = "gif"
        avatar_url = f"https://cdn.discordapp.com/avatars/{discord_id}/{avatar_hash}.{avatar_format}"
        
    return {
        "discord_id": discord_id,
        "name": username,
        "avatar": avatar_url
    }

def create_user_session(
    db: Session, 
    user: User, 
    provider: AuthProvider, 
    request: Request
) -> Tuple[str, UserInfo]:
    """Create a user session and return token + user info"""
    user_agent = request.headers.get("user-agent")
    client_host = request.client.host if request.client else None
    
    # Create a user session
    user_session = UserRepository.create_session(
        db=db,
        user_id=user.id,
        provider=provider,
        ip_address=client_host,
        user_agent=user_agent
    )
    
    # Create user info response
    user_info = user_to_response(user)
    
    # Create a signed token with the user info and session token
    token = create_token(user_info.model_dump(), user_session.session_token)
    
    return token, user_info

def handle_account_linking(
    db: Session,
    link_token: Optional[str], 
    provider: AuthProvider,
    auth_id: str,
    name: Optional[str] = None,
    avatar_url: Optional[str] = None,
    force_link: bool = False,
    steam_data: Optional[Dict[str, str]] = None
) -> Tuple[Optional[User], bool, Optional[dict]]:
    """
    Handle linking of a new authentication provider to an existing account.
    Returns (user, success, error_detail) where:
    - user is the User object (can be None if linking failed)
    - success is True if linking was successful or no linking was required
    - error_detail is a dict with error details (None if no error)
    """
    # Check if we're linking accounts
    link_user_id = None
    error_detail = None
    
    if link_token:
        try:
            link_token_data = serializer.loads(link_token)
            if "user" in link_token_data and "session_token" in link_token_data:
                # Verify the session
                session = UserRepository.get_session(db, link_token_data["session_token"])
                if session:
                    link_user_id = session.user_id
        except Exception:
            # Invalid link token, proceed with normal login
            pass
    
    # If we're linking an account and the user is authenticated
    if link_user_id:
        # Get the current user we want to link to
        current_user = UserRepository.get_user_by_id(db, link_user_id)
        if not current_user:
            return None, False, {"message": "User not found"}
        
        # Check if this auth account is already linked to someone else
        existing_user = UserRepository.get_user_by_auth_id(db, provider, auth_id)
        
        # If force linking is enabled and account is already linked to someone else
        if force_link and existing_user and existing_user.id != link_user_id:
            try:
                # Unlink from existing user first
                if provider == "steam":
                    existing_user.steam_id = None
                elif provider == "discord":
                    existing_user.discord_id = None
                
                db.commit()
                
                # Now link it to the current user
                if provider == "steam":
                    current_user.steam_id64 = auth_id  # Primary identifier (SteamID64)
                    
                    # Also store additional Steam ID formats if provided
                    if steam_data:
                        current_user.steam_id = steam_data.get("steam_id")
                        current_user.steam_id3 = steam_data.get("steam_id3")
                        current_user.steam_profile_url = steam_data.get("steam_profile_url")
                elif provider == "discord":
                    current_user.discord_id = auth_id
                
                # Update profile data if available
                if name and not current_user.name:
                    current_user.name = name
                if avatar_url and not current_user.avatar_url:
                    current_user.avatar_url = avatar_url
                
                db.commit()
                db.refresh(current_user)
                return current_user, True, None
            except Exception as e:
                return None, False, {"message": f"Failed to force link account: {str(e)}"}
        else:
            # Normal linking (non-force)
            user, success = UserRepository.link_account(
                db=db,
                user_id=link_user_id,
                provider=provider,
                auth_id=auth_id,
                name=name,
                avatar_url=avatar_url,
                steam_data=steam_data if provider == "steam" else None
            )
            
            if not success and not force_link:
                # Account already linked to a different user and we're not forcing the link
                error_detail = {
                    "message": f"This {provider} account is already linked to a different user",
                    "error_code": f"{provider}_account_already_linked",
                    "auth_id": auth_id,
                    "linked_to_user_id": existing_user.id if existing_user else None,
                }
                
                if provider == "steam" and link_token:
                    error_detail["force_link_url"] = f"{settings.STEAM_OPENID_REALM}/auth/steam/login?link_token={quote_plus(link_token)}&force=true"
                
                return user, False, error_detail
            
            return user, success, None
    
    # No linking - regular login
    return None, True, None

def logout_user(db: Session, token: str) -> bool:
    """Logout a user by invalidating their session"""
    try:
        # Load token data
        token_data = serializer.loads(token)
        
        # Check if it's the new token format with session
        if isinstance(token_data, dict) and "session_token" in token_data:
            session_token = token_data["session_token"]
            
            # Invalidate the session
            return UserRepository.invalidate_session(db, session_token)
        
        return False
    except Exception:
        return False