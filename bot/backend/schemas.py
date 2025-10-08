from typing import Optional, Dict, Any, List, Literal
from pydantic import BaseModel, field_validator, HttpUrl, ConfigDict, Field

# Authentication models
class AuthProvider(BaseModel):
    """Model for authentication provider information"""
    provider: Literal["steam", "discord"]
    provider_id: str
    linked: bool

class UserInfo(BaseModel):
    """Model for user information"""
    id: Optional[int] = None
    steam_id64: Optional[str] = None  # Primary Steam ID (64-bit format)
    steam_id: Optional[str] = None    # Legacy Steam ID format (for backwards compatibility)
    steam_id3: Optional[str] = None   # Steam ID3 format
    steam_profile_url: Optional[str] = None  # Steam community profile URL
    discord_id: Optional[str] = None
    name: Optional[str] = None
    avatar: Optional[HttpUrl] = None
    auth_providers: List[AuthProvider] = []
    
    @field_validator('steam_id')
    @classmethod
    def validate_steam_id(cls, v):
        """Validate the Steam ID format if present"""
        if v is not None:
            # Allow traditional STEAM_X:Y:Z format
            if v.startswith('STEAM_') and ':' in v:
                # Validate the format using regex
                import re
                if not re.match(r'^STEAM_[0-9]:[0-9]:[0-9]+$', v):
                    raise ValueError('Invalid Steam ID format. Expected STEAM_X:Y:Z where X, Y, and Z are numeric.')
            # For numeric-only IDs
            elif not v.isdigit():
                raise ValueError('Steam ID must be a numeric string or in STEAM_X:Y:Z format')
        return v

    @field_validator('steam_id64')
    @classmethod
    def validate_steam_id64(cls, v):
        """Validate the Steam ID format if present"""
        if v is not None and not v.isdigit():
            raise ValueError('Steam ID64 must be a numeric string')
        return v
    
    def model_dump(self, *args, **kwargs):
        """Override model_dump to convert HttpUrl to string for serialization"""
        data = super().model_dump(*args, **kwargs)
        # Convert HttpUrl to string
        if data.get('avatar') is not None:
            data['avatar'] = str(data['avatar'])
        return data

class TokenRequest(BaseModel):
    """Request model for token verification"""
    token: str

class LinkAccountRequest(BaseModel):
    """Request model for linking accounts"""
    token: str
    provider: Literal["steam", "discord"]

class MessageResponse(BaseModel):
    """Model for API responses containing a message"""
    message: str

class OpenIDParams(BaseModel):
    """Model for OpenID parameters"""
    ns: str = Field(default="http://specs.openid.net/auth/2.0", alias="openid.ns")
    mode: str = Field(alias="openid.mode")
    return_to: Optional[str] = Field(None, alias="openid.return_to")
    realm: Optional[str] = Field(None, alias="openid.realm")
    identity: Optional[str] = Field(None, alias="openid.identity")
    claimed_id: Optional[str] = Field(None, alias="openid.claimed_id")
    
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True
    )