import httpx
from typing import Optional
from fastapi import HTTPException, Request
from pydantic import BaseModel
from .config import settings

class AuthenticatedUser(BaseModel):
    """User information from authentication"""
    user_id: int
    name: Optional[str] = None
    discord_id: Optional[str] = None
    steam_id64: Optional[str] = None
    is_authenticated: bool = True

class AuthClient:
    """HTTP client for authenticating with the main website API"""
    
    def __init__(self):
        self.website_base_url = str(settings.website_base_url).rstrip('/')
        self.client = httpx.AsyncClient(timeout=10.0)
    
    async def validate_session(self, session_token: str) -> Optional[AuthenticatedUser]:
        """
        Validate a session cookie by calling the website's API
        Returns user info if valid, None if invalid
        """
        try:
            response = await self.client.get(
                f"{self.website_base_url}/api/validate/session",
                cookies={"session_token": session_token}
            )
            
            if response.status_code == 200:
                user_data = response.json()
                return AuthenticatedUser(**user_data)
            elif response.status_code == 401:
                return None  # Invalid/expired session
            else:
                # Unexpected error from website API
                print(f"Website API error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"Error validating session: {e}")
            return None
    
    async def get_current_user(self, request: Request) -> Optional[AuthenticatedUser]:
        """
        Get current user from request session cookie
        Returns user info if authenticated, None if not
        """
        session_token = request.cookies.get("session_token")
        if not session_token:
            return None
        
        return await self.validate_session(session_token)
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()

# Global auth client instance
auth_client = AuthClient()

async def get_current_user(request: Request) -> Optional[AuthenticatedUser]:
    """
    FastAPI dependency to get current authenticated user
    Returns None if not authenticated (doesn't raise exception)
    """
    return await auth_client.get_current_user(request)

async def require_auth(request: Request) -> AuthenticatedUser:
    """
    FastAPI dependency that requires authentication
    Raises 401 HTTPException if not authenticated
    """
    user = await auth_client.get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user