from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from urllib.parse import urlencode, quote_plus

from website.app.core.config import settings
from website.app.core.sessions import (
    get_current_user_from_session, 
    create_session_cookie, 
    clear_session_cookie,
    validate_csrf_token
)
from shared.database import get_db
from shared.repositories import UserRepository
from website.app.services import auth_service
from website.app.models.auth import OpenIDParams


router = APIRouter(prefix="/auth", tags=["Web Authentication"])

@router.get("/discord/login")
async def discord_login():
    """Initiate Discord OAuth2 authentication"""
    params = {
        "client_id": settings.DISCORD_APPLICATION_ID,
        "redirect_uri": str(settings.DISCORD_CALLBACK_URL),
        "response_type": "code",
        "scope": "identify",
    }
    
    auth_url = f"{settings.DISCORD_OAUTH_URL}?{urlencode(params)}"
    return RedirectResponse(url=auth_url)

@router.get("/discord/callback")
async def discord_callback(
    request: Request,
    code: str,
    state: str = None,
    db: Session = Depends(get_db)
):
    """Handle Discord OAuth2 callback and create session"""
    try:
        # Get Discord user information
        discord_user = await auth_service.exchange_discord_code(code)
        user_data = auth_service.process_discord_user_data(discord_user)
        
        # Validate discord_id is not None
        discord_id = user_data["discord_id"]
        if not discord_id:
            return RedirectResponse(url="/?error=Invalid Discord user data")
        
        # Create or update user
        user = UserRepository.create_or_update_user(
            db=db,
            provider="discord",
            auth_id=discord_id,
            name=user_data["name"],
            avatar_url=user_data["avatar"]
        )
        
        # Create session using UserRepository directly
        user_session = UserRepository.create_session(
            db=db,
            user_id=user.id,
            provider="discord",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent")
        )
        
        # Create response and set session cookie
        # Check if we should redirect to external service via state parameter
        external_return = None
        if state:
            try:
                import base64
                import json
                # Decode state parameter
                state_json = base64.urlsafe_b64decode(state.encode()).decode()
                state_data = json.loads(state_json)
                external_return = state_data.get("return_to")
            except Exception as e:
                print(f"Error decoding state parameter: {e}")
                # Continue with normal flow if state decoding fails
        # TODO: Roll back this development vs production hack once pugs.lumabyte.io and fastdl.pugs.lumabyte.io subdomains have propagated
        # Note to self: make sure newt is forwarding the above subdomains to both the website and fastdl running processes locally
        if external_return:
            # For development: pass session token as query param for cross-port auth
            # For production: this won't be needed due to shared domain cookies
            from urllib.parse import urlencode, urlparse, parse_qs
            if settings.environment == "development":
                # Add session token to the return URL
                separator = "&" if "?" in external_return else "?"
                external_return_with_token = f"{external_return}{separator}session_token={user_session.session_token}"
                response = RedirectResponse(url=external_return_with_token)
            else:
                response = RedirectResponse(url=external_return)
        else:
            response = RedirectResponse(url="/?success=Login successful")
        
        create_session_cookie(response, user_session.session_token)
        
        return response
        
    except Exception as e:
        return RedirectResponse(url=f"/?error=Login failed: {str(e)}")

@router.post("/logout")
async def logout(
    request: Request,
    csrf_token: str = Form(...),
    db: Session = Depends(get_db)
):
    """Logout user by clearing session"""
    # Validate CSRF token
    if not validate_csrf_token(request, csrf_token):
        return RedirectResponse(url="/?error=Invalid request")
    
    # Get current session
    session_token = request.cookies.get("session_token")
    if session_token:
        # Invalidate session in database
        UserRepository.invalidate_session(db, session_token)
    
    # Clear session cookie and redirect
    response = RedirectResponse(url="/?success=Logged out successfully")
    clear_session_cookie(response)
    
    return response

@router.post("/steam/link")
async def link_steam_account(
    request: Request,
    csrf_token: str = Form(...),
    db: Session = Depends(get_db)
):
    """Initiate Steam account linking"""
    # Validate CSRF token
    if not validate_csrf_token(request, csrf_token):
        return RedirectResponse(url="/profile?error=Invalid request", status_code=303)
    
    # Check if user is authenticated
    user = get_current_user_from_session(request, db)
    if not user:
        return RedirectResponse(url="/?error=Authentication required")
    
    # Check if Steam is already linked
    if user.steam_id64:
        return RedirectResponse(url="/profile?error=Steam account already linked", status_code=303)
    
    # Create Steam OpenID authentication URL
    
    # Create link token using current session token
    session_token = request.cookies.get("session_token")
    if not session_token:
        return RedirectResponse(url="/profile?error=Session token not found", status_code=303)
    
    params = OpenIDParams(
        **{
            "openid.ns": "http://specs.openid.net/auth/2.0",
            "openid.mode": "checkid_setup",
            "openid.return_to": f"{settings.STEAM_OPENID_CALLBACK_URL}?link_token={quote_plus(session_token)}",
            "openid.realm": str(settings.STEAM_OPENID_REALM),
            "openid.identity": "http://specs.openid.net/auth/2.0/identifier_select",
            "openid.claimed_id": "http://specs.openid.net/auth/2.0/identifier_select"
        }
    )
    
    params_dict = {k: str(v) for k, v in params.model_dump(by_alias=True).items() if v is not None}
    auth_url = f"{settings.STEAM_OPENID_URL}?{urlencode(params_dict)}"
    
    return RedirectResponse(url=auth_url)

@router.get("/steam/callback")
async def steam_callback(request: Request, db: Session = Depends(get_db)):
    """Handle Steam OpenID callback for account linking"""
    query_params = dict(request.query_params)
    
    try:
        # Convert query params to OpenIDParams for validation
        openid_params = OpenIDParams(**{
            "openid.mode": query_params.get("openid.mode", ""),
            "openid.op_endpoint": query_params.get("openid.op_endpoint"),
            "openid.claimed_id": query_params.get("openid.claimed_id"),
            "openid.identity": query_params.get("openid.identity"),
            "openid.return_to": query_params.get("openid.return_to"),
            "openid.realm": query_params.get("openid.realm"),
            "openid.response_nonce": query_params.get("openid.response_nonce"),
            "openid.assoc_handle": query_params.get("openid.assoc_handle"),
            "openid.signed": query_params.get("openid.signed"),
            "openid.sig": query_params.get("openid.sig")
        })
        
        # Validate Steam authentication
        steam_id64 = await auth_service.validate_steam_auth(openid_params)
        steam_user_data = await auth_service.get_steam_user_info(steam_id64)
        
        # Get link token and validate session
        link_token = query_params.get("link_token")
        if not link_token:
            return RedirectResponse(url="/profile?error=Invalid linking request", status_code=303)
        
        # Verify session is valid
        session = UserRepository.get_session(db, link_token)
        if not session:
            return RedirectResponse(url="/?error=Session expired")
        
        user = UserRepository.get_user_by_id(db, session.user_id)
        if not user:
            return RedirectResponse(url="/?error=User not found")
        
        # Check if Steam account is already linked to someone else
        existing_steam_user = UserRepository.get_user_by_auth_id(db, "steam", steam_id64)
        if existing_steam_user and existing_steam_user.id != user.id:
            return RedirectResponse(url="/profile?error=Steam account is already linked to another user", status_code=303)
        
        # Link Steam account
        user.steam_id64 = steam_id64
        user.steam_id = steam_user_data.steam_id
        user.steam_id3 = steam_user_data.steam_id3
        user.steam_profile_url = steam_user_data.steam_profile_url
        
        # Update profile data if needed
        if steam_user_data.name and not user.name:
            user.name = steam_user_data.name
        
        db.commit()
        
        return RedirectResponse(url="/profile?success=Steam account linked successfully", status_code=303)
        
    except Exception as e:
        return RedirectResponse(url=f"/profile?error=Steam linking failed: {str(e)}", status_code=303)

@router.post("/unlink")
async def unlink_account(
    request: Request,
    provider: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db)
):
    """Unlink an authentication provider"""
    # Validate CSRF token
    if not validate_csrf_token(request, csrf_token):
        return RedirectResponse(url="/profile?error=Invalid request", status_code=303)
    
    # Check if user is authenticated
    user = get_current_user_from_session(request, db)
    if not user:
        return RedirectResponse(url="/?error=Authentication required")
    
    # Prevent unlinking Discord (primary account)
    if provider == "discord":
        return RedirectResponse(url="/profile?error=Discord account cannot be unlinked", status_code=303)
    
    # Check if Steam is linked
    if provider == "steam" and not user.steam_id64:
        return RedirectResponse(url="/profile?error=No Steam account linked", status_code=303)
    
    try:
        # Unlink Steam account
        if provider == "steam":
            user.steam_id64 = None
            user.steam_id = None
            user.steam_id3 = None
            user.steam_profile_url = None
            db.commit()
        
        return RedirectResponse(url="/profile?success=Account unlinked successfully", status_code=303)
        
    except Exception as e:
        return RedirectResponse(url=f"/profile?error=Unlinking failed: {str(e)}", status_code=303)

@router.post("/sync-steam")
async def sync_steam_data(
    request: Request,
    csrf_token: str = Form(...),
    db: Session = Depends(get_db)
):
    """Sync Steam user data from Steam API"""
    # Validate CSRF token
    if not validate_csrf_token(request, csrf_token):
        return RedirectResponse(url="/profile?error=Invalid request", status_code=303)
    
    # Check if user is authenticated
    user = get_current_user_from_session(request, db)
    if not user:
        return RedirectResponse(url="/?error=Authentication required")
    
    # Check if Steam is linked
    if not user.steam_id64:
        return RedirectResponse(url="/profile?error=No Steam account linked", status_code=303)
    
    try:
        # Fetch updated Steam data
        steam_user_data = await auth_service.get_steam_user_info(user.steam_id64)
        
        if not steam_user_data:
            return RedirectResponse(url="/profile?error=Failed to retrieve Steam data", status_code=303)
        
        # Update user with fresh Steam data
        user.steam_id = steam_user_data.steam_id
        user.steam_id3 = steam_user_data.steam_id3
        user.steam_profile_url = steam_user_data.steam_profile_url
        
        # Update profile data
        if steam_user_data.name:
            user.name = steam_user_data.name
        
        db.commit()
        
        return RedirectResponse(url="/profile?success=Steam data synced successfully", status_code=303)
        
    except Exception as e:
        return RedirectResponse(url=f"/profile?error=Steam sync failed: {str(e)}", status_code=303)

@router.get("/redirect-login")
async def redirect_login(return_to: str = None):
    """Initiate Discord OAuth2 authentication with return URL for external services"""
    import base64
    import json
    
    # Use the original callback URL without modifications
    callback_url = str(settings.DISCORD_CALLBACK_URL)
    
    # Create state parameter with return URL
    state_data = {}
    if return_to:
        state_data["return_to"] = return_to
    
    # Encode state as base64 JSON (if we have data to encode)
    state = None
    if state_data:
        state_json = json.dumps(state_data)
        state = base64.urlsafe_b64encode(state_json.encode()).decode()
    
    params = {
        "client_id": settings.DISCORD_APPLICATION_ID,
        "redirect_uri": callback_url,
        "response_type": "code",
        "scope": "identify",
    }
    
    # Add state parameter if we have one
    if state:
        params["state"] = state
    
    auth_url = f"{settings.DISCORD_OAUTH_URL}?{urlencode(params)}"
    return RedirectResponse(url=auth_url)