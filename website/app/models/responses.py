from pydantic import BaseModel, ConfigDict
from typing import Optional
from app.models.auth import UserInfo

class HomePageContext(BaseModel):
    """Template context for home page"""
    user: Optional[UserInfo] = None
    error: Optional[str] = None
    success: Optional[str] = None
    csrf_token: str
    
    model_config = ConfigDict(arbitrary_types_allowed=True)