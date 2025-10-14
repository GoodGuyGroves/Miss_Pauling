from pydantic import BaseModel, ConfigDict
from typing import Optional
from website.app.models.auth import UserInfo

class HomePageContext(BaseModel):
    """Template context for home page"""
    user: Optional[UserInfo] = None
    error: Optional[str] = None
    success: Optional[str] = None
    csrf_token: str
    
    model_config = ConfigDict(arbitrary_types_allowed=True)

class UserValidationResponse(BaseModel):
    """Response model for API token validation"""
    user_id: int
    name: Optional[str] = None
    discord_id: Optional[str] = None
    steam_id64: Optional[str] = None
    is_authenticated: bool = True
    
    model_config = ConfigDict(from_attributes=True)