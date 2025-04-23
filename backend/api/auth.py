from fastapi import APIRouter, Depends, HTTPException, Query, Request, Form
from fastapi.responses import RedirectResponse
import json
from sqlalchemy.orm import Session
from datetime import datetime
from urllib.parse import urlencode, quote_plus
import httpx

from app.schemas import (
    OpenIDParams, MessageResponse, UserInfo, TokenRequest, 
    LinkAccountRequest
)
from app.db.database import get_db  
from app.db.repositories import UserRepository
from app.core.config import get_settings
from app.core.security import serializer, verify_token as verify_auth_token, user_to_response
from app.services import auth_service
from typing import Optional

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.get("/steam/login")
async def steam_login(link_token: Optional[str] = None, force: bool = False):
    """Initiate Steam OpenID authentication (only for account linking, not direct login)"""
    # Prevent direct login with Steam - only allow account linking
    if not link_token:
        # Redirect users trying to log in directly with Steam to the Discord login
        return RedirectResponse(url=f"{settings.frontend_url}?error=steam_login_disabled")
        
    # Create OpenID parameters using Pydantic model
    params = OpenIDParams(
        **{
            "openid.ns": "http://specs.openid.net/auth/2.0",
            "openid.mode": "checkid_setup",
            "openid.return_to": settings.return_to,
            "openid.realm": settings.realm,
            "openid.identity": "http://specs.openid.net/auth/2.0/identifier_select",
            "openid.claimed_id": "http://specs.openid.net/auth/2.0/identifier_select"
        }
    )
    
    # Add link token to return_to URL and include force parameter if specified
    url_params = {"link_token": quote_plus(link_token)}
    if force:
        url_params["force"] = "true"
    
    # Build the return_to URL with parameters
    return_to_with_params = f"{settings.return_to}?" + urlencode(url_params)
    params.return_to = return_to_with_params
    
    # Convert Pydantic model to dictionary and format URL parameters
    params_dict = {k: str(v) for k, v in params.model_dump(by_alias=True).items() if v is not None}
    auth_url = f"{settings.steam_openid_url}?{urlencode(params_dict)}"
    return RedirectResponse(url=auth_url)

@router.get("/steam/callback")
async def steam_callback(request: Request, db: Session = Depends(get_db)):
    """Handle Steam OpenID callback and validate authentication (only for account linking)"""
    params = dict(request.query_params)
    
    # Validate Steam authentication
    try:
        # Steam ID from OpenID is SteamID64 format
        steam_id64 = await auth_service.validate_steam_auth(params)
        
        # Get complete Steam user data including different ID formats
        steam_user_data = await auth_service.get_steam_user_info(steam_id64)
        
        # Check if we're linking accounts
        link_token = params.get("link_token")
        
        # Prevent direct login with Steam - require link_token
        if not link_token:
            error_json = json.dumps({
                "message": "Direct Steam login is disabled. Please log in with Discord first.",
                "status": 403
            })
            encoded_error = quote_plus(error_json)
            error_redirect_url = f"{settings.frontend_url}?error={encoded_error}"
            return RedirectResponse(url=error_redirect_url)
        
        force_link = params.get("force") == "true"
        
        linked_user, linking_success, error_details = auth_service.handle_account_linking(
            db=db,
            link_token=link_token,
            provider="steam",
            auth_id=steam_id64,  # Use steam_id64 as the primary identifier
            name=steam_user_data.get("name"),
            avatar_url=steam_user_data.get("avatar_url") or steam_user_data.get("avatar"),
            force_link=force_link,
            steam_data={  # Pass all Steam ID formats
                "steam_id": steam_user_data.get("steam_id"),
                "steam_id3": steam_user_data.get("steam_id3"),
                "steam_profile_url": steam_user_data.get("steam_profile_url")
            }
        )
        
        # If we have error details during linking, redirect with error
        if error_details:
            error_json = json.dumps(error_details)
            encoded_error = quote_plus(error_json)
            error_redirect_url = f"{settings.frontend_url}/auth-callback?error={encoded_error}"
            return RedirectResponse(url=error_redirect_url)
        
        # If we successfully linked an account
        if linked_user:
            token, user_info = auth_service.create_user_session(db, linked_user, "discord", request)
            # Redirect back to frontend with token
            redirect_url = f"{settings.frontend_url}/auth-callback?token={quote_plus(token)}"
            return RedirectResponse(url=redirect_url)
        else:
            # Should never get here since we require link_token
            error_json = json.dumps({
                "message": "Something went wrong with account linking",
                "status": 400
            })
            encoded_error = quote_plus(error_json)
            error_redirect_url = f"{settings.frontend_url}?error={encoded_error}"
            return RedirectResponse(url=error_redirect_url)
        
    except HTTPException as e:
        # Handle errors by redirecting to frontend with error details
        error_json = json.dumps({"message": e.detail, "status": e.status_code})
        encoded_error = quote_plus(error_json)
        error_redirect_url = f"{settings.frontend_url}/auth-callback?error={encoded_error}"
        return RedirectResponse(url=error_redirect_url)

@router.get("/discord/login")
async def discord_login(link_token: Optional[str] = None):
    """Initiate Discord OAuth2 authentication"""
    # Create Discord OAuth2 parameters
    params = {
        "client_id": settings.discord_client_id,
        "redirect_uri": settings.discord_redirect_uri,
        "response_type": "code",
        "scope": "identify",
    }
    
    # If link_token is provided, we're linking an account
    if link_token:
        # Store the link token in a state parameter for verification on callback
        state = serializer.dumps({"link_token": link_token})
        params["state"] = state
    
    # Generate OAuth2 URL
    auth_url = f"{settings.discord_oauth_url}?{urlencode(params)}"
    return RedirectResponse(url=auth_url)

@router.get("/discord/callback")
async def discord_callback(
    request: Request,
    code: str = Query(...),
    state: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Handle Discord OAuth2 callback and validate authentication"""
    try:
        # Get Discord user information
        discord_user = await auth_service.exchange_discord_code(code)
        
        # Process Discord user data
        user_data = auth_service.process_discord_user_data(discord_user)
        
        # Check if we're linking accounts
        link_user_id = None
        link_token = None
        if state:
            try:
                state_data = serializer.loads(state)
                if "link_token" in state_data:
                    link_token = state_data["link_token"]
            except Exception:
                # Invalid state token, proceed with normal login
                pass
        
        # Handle account linking if requested
        linked_user, linking_success, error_details = auth_service.handle_account_linking(
            db=db,
            link_token=link_token,
            provider="discord",
            auth_id=user_data["discord_id"],
            name=user_data["name"],
            avatar_url=user_data["avatar"]
        )
        
        # If we have error details during linking, redirect with error
        if error_details:
            error_json = json.dumps(error_details)
            encoded_error = quote_plus(error_json)
            error_redirect_url = f"{settings.frontend_url}/auth-callback?error={encoded_error}"
            return RedirectResponse(url=error_redirect_url)
        
        # If we successfully linked an account
        if linked_user:
            token, user_info = auth_service.create_user_session(db, linked_user, "discord", request)
        else:
            # Normal login with Discord
            user = UserRepository.create_or_update_user(
                db=db,
                provider="discord",
                auth_id=user_data["discord_id"],
                name=user_data["name"],
                avatar_url=user_data["avatar"]
            )
            
            token, user_info = auth_service.create_user_session(db, user, "discord", request)
        
        # Redirect back to frontend with token
        redirect_url = f"{settings.frontend_url}/auth-callback?token={quote_plus(token)}"
        return RedirectResponse(url=redirect_url)
        
    except HTTPException as e:
        # Handle errors by redirecting to frontend with error details
        error_json = json.dumps({"message": e.detail, "status": e.status_code})
        encoded_error = quote_plus(error_json)
        error_redirect_url = f"{settings.frontend_url}/auth-callback?error={encoded_error}"
        return RedirectResponse(url=error_redirect_url)

@router.get("/verify-token", response_model=UserInfo)
async def verify_token(token: str, db: Session = Depends(get_db)):
    """Verify the authentication token and return user info"""
    try:
        # Load token data
        token_data = verify_auth_token(token)
        
        # Handle both old token format and new token format
        if isinstance(token_data, dict) and "user" in token_data and "session_token" in token_data:
            # New token format with session token
            session_token = token_data["session_token"]
            
            # Verify session is still valid
            session = UserRepository.get_session(db, session_token)
            if not session:
                raise HTTPException(status_code=401, detail="Session expired or invalid")
                
            # Get latest user data from database
            user = UserRepository.get_user_by_id(db, session.user_id)
            if not user:
                raise HTTPException(status_code=401, detail="User not found")
                
            # Return user data from database
            return user_to_response(user)
        else:
            # Old token format - for backward compatibility
            # Validate the data with Pydantic
            return UserInfo(**token_data)
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid user data in token: {str(e)}")

@router.post("/logout")
async def logout(token_request: TokenRequest, db: Session = Depends(get_db)):
    """Logout user by invalidating their session"""
    success = auth_service.logout_user(db, token_request.token)
    if not success:
        raise HTTPException(status_code=400, detail="Session not found or already invalidated")
    
    return {"message": "Logout successful"}

@router.post("/link/request", response_model=MessageResponse)
async def request_account_linking(
    link_request: LinkAccountRequest,
    db: Session = Depends(get_db)
):
    """Request to link a new authentication provider to an existing account"""
    try:
        # Validate the token
        token_data = verify_auth_token(link_request.token)
        
        if not isinstance(token_data, dict) or "session_token" not in token_data or "user" not in token_data:
            raise HTTPException(status_code=401, detail="Invalid authentication token format")
            
        # Verify the session is still valid
        session = UserRepository.get_session(db, token_data["session_token"])
        if not session:
            raise HTTPException(status_code=401, detail="Session expired or invalid")
            
        # Get the user
        user = UserRepository.get_user_by_id(db, session.user_id)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
            
        # Check if requested provider is already linked - updated to check steam_id64 instead of steam_id
        if link_request.provider == "steam" and user.steam_id64:
            return MessageResponse(message="Steam account is already linked to this user")
            
        if link_request.provider == "discord" and user.discord_id:
            return MessageResponse(message="Discord account is already linked to this user")
        
        # Redirect to appropriate login endpoint with the link token
        if link_request.provider == "steam":
            return MessageResponse(
                message=f"{settings.realm}/auth/steam/login?link_token={quote_plus(link_request.token)}"
            )
        elif link_request.provider == "discord":
            return MessageResponse(
                message=f"{settings.realm}/auth/discord/login?link_token={quote_plus(link_request.token)}"
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported provider: {link_request.provider}")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Account linking request failed: {str(e)}")

@router.get("/link/status", response_model=UserInfo)
async def check_linked_accounts(token: str, db: Session = Depends(get_db)):
    """Check the status of linked accounts for a user"""
    try:
        # Validate the token
        token_data = verify_auth_token(token)
        
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
            
        # Return current user info with linked accounts status
        return user_to_response(user)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check account status: {str(e)}")

@router.post("/unlink", response_model=UserInfo)
async def unlink_account(
    link_request: LinkAccountRequest,
    db: Session = Depends(get_db)
):
    """Unlink an authentication provider from a user account"""
    try:
        # Validate the token
        token_data = verify_auth_token(link_request.token)
        
        if not isinstance(token_data, dict) or "session_token" not in token_data or "user" not in token_data:
            raise HTTPException(status_code=401, detail="Invalid authentication token format")
            
        # Verify the session is still valid
        session = UserRepository.get_session(db, token_data["session_token"])
        if not session:
            raise HTTPException(status_code=401, detail="Session expired or invalid")
            
        # Get the user
        user = UserRepository.get_user_by_id(db, session.user_id)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
            
        # Check if requested provider is Discord - which we no longer allow to be unlinked
        if link_request.provider == "discord":
            raise HTTPException(status_code=400, detail="Discord account cannot be unlinked as it is mandatory for authentication")
            
        # Check if requested provider is linked - updated to check steam_id64 instead of steam_id
        if link_request.provider == "steam" and not user.steam_id64:
            raise HTTPException(status_code=400, detail="No Steam account is linked to this user")
        
        # Attempt to unlink the account
        user, success, requires_logout = UserRepository.unlink_account(db, user.id, link_request.provider)
        
        if not success:
            raise HTTPException(status_code=400, detail=f"Failed to unlink {link_request.provider} account")
            
        # Add the requires_logout flag to the response
        response_data = user_to_response(user).dict()
        response_data["requires_logout"] = requires_logout
            
        # Return updated user info with the logout flag
        return response_data
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Account unlinking failed: {str(e)}")

@router.post("/force-link-steam", response_model=UserInfo)
async def force_link_steam(
    request: Request,
    db: Session = Depends(get_db)
):
    """Force link a Steam account to the current user without requiring re-authentication"""
    try:
        # Parse request body
        data = await request.json()
        token = data.get("token")
        steam_id64 = data.get("steam_id")  # This is the SteamID64 format
        
        if not token or not steam_id64:
            raise HTTPException(status_code=400, detail="Missing required fields")
        
        # Validate the token
        token_data = verify_auth_token(token)
            
        if not isinstance(token_data, dict) or "session_token" not in token_data or "user" not in token_data:
            raise HTTPException(status_code=401, detail="Invalid authentication token format")
            
        # Verify the session is still valid
        session = UserRepository.get_session(db, token_data["session_token"])
        if not session:
            raise HTTPException(status_code=401, detail="Session expired or invalid")
            
        # Get the current user we want to link to
        current_user = UserRepository.get_user_by_id(db, session.user_id)
        if not current_user:
            raise HTTPException(status_code=404, detail="User not found")
            
        # Check if this Steam account is already linked to someone else
        existing_user = UserRepository.get_user_by_auth_id(db, "steam", steam_id64)
        
        # If Steam account is already linked to this user, just return success
        if existing_user and existing_user.id == current_user.id:
            return user_to_response(current_user)
            
        # If Steam account is linked to a different user, force unlink it
        if existing_user and existing_user.id != current_user.id:
            try:
                # First manually unlink the Steam account from the existing user
                existing_user.steam_id64 = None
                existing_user.steam_id = None
                existing_user.steam_id3 = None
                existing_user.steam_profile_url = None
                db.commit()
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to unlink Steam account: {str(e)}")
        
        # Now link the Steam ID to the current user
        try:
            # Fetch all Steam user data including multiple ID formats
            steam_user_data = await auth_service.get_steam_user_info(steam_id64)
            
            if not steam_user_data:
                raise HTTPException(status_code=500, detail="Failed to retrieve Steam user data")
                
            # Link the Steam account to the current user with all formats
            current_user.steam_id64 = steam_id64
            current_user.steam_id = steam_user_data.get("steam_id")
            current_user.steam_id3 = steam_user_data.get("steam_id3")
            current_user.steam_profile_url = steam_user_data.get("steam_profile_url")
            
            # Update profile data if available and needed
            if steam_user_data.get("name") and not current_user.name:
                current_user.name = steam_user_data.get("name")
            if steam_user_data.get("avatar_url") and not current_user.avatar_url:
                current_user.avatar_url = steam_user_data.get("avatar_url")
                
            db.commit()
            db.refresh(current_user)
            
            # Return the updated user info
            return user_to_response(current_user)
            
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to link Steam account: {str(e)}")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to force link Steam account: {str(e)}")

@router.post("/sync-steam", response_model=UserInfo)
async def sync_steam_data(
    token_request: TokenRequest,
    db: Session = Depends(get_db)
):
    """Sync Steam user data from the Steam API"""
    try:
        # Validate the token
        token_data = verify_auth_token(token_request.token)
        
        if not isinstance(token_data, dict) or "session_token" not in token_data or "user" not in token_data:
            raise HTTPException(status_code=401, detail="Invalid authentication token format")
            
        # Verify the session is still valid
        session = UserRepository.get_session(db, token_data["session_token"])
        if not session:
            raise HTTPException(status_code=401, detail="Session expired or invalid")
            
        # Get the user
        user = UserRepository.get_user_by_id(db, session.user_id)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
            
        # Check if user has a linked Steam account
        if not user.steam_id64:
            raise HTTPException(status_code=400, detail="No Steam account is linked to this user")
        
        # Fetch updated Steam user data
        try:
            steam_user_data = await auth_service.get_steam_user_info(user.steam_id64)
            
            if not steam_user_data:
                raise HTTPException(status_code=500, detail="Failed to retrieve Steam user data")
                
            # Update the user with fresh Steam data
            user.steam_id = steam_user_data.get("steam_id")
            user.steam_id3 = steam_user_data.get("steam_id3")
            user.steam_profile_url = steam_user_data.get("steam_profile_url")
            
            # Update profile data like username and avatar if available from Steam
            if steam_user_data.get("name"):
                user.name = steam_user_data.get("name")
            if steam_user_data.get("avatar_url"):
                user.avatar_url = steam_user_data.get("avatar_url")
                
            db.commit()
            db.refresh(user)
            
            # Return the updated user info
            return user_to_response(user)
            
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to sync Steam account data: {str(e)}")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Steam data sync failed: {str(e)}")