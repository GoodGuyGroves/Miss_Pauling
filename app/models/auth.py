from typing import Optional, List, Literal
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
    """Complete OpenID 2.0 parameters for Steam authentication"""
    ns: str = Field(default="http://specs.openid.net/auth/2.0", alias="openid.ns")
    mode: str = Field(alias="openid.mode")
    op_endpoint: Optional[str] = Field(None, alias="openid.op_endpoint")
    claimed_id: Optional[str] = Field(None, alias="openid.claimed_id")
    identity: Optional[str] = Field(None, alias="openid.identity")
    return_to: Optional[str] = Field(None, alias="openid.return_to")
    realm: Optional[str] = Field(None, alias="openid.realm")
    response_nonce: Optional[str] = Field(None, alias="openid.response_nonce")
    assoc_handle: Optional[str] = Field(None, alias="openid.assoc_handle")
    signed: Optional[str] = Field(None, alias="openid.signed")
    sig: Optional[str] = Field(None, alias="openid.sig")
    
    @field_validator('claimed_id')
    @classmethod
    def validate_steam_claimed_id(cls, v):
        if v and not (v.startswith('https://steamcommunity.com/openid/id/') or 
                     v == 'http://specs.openid.net/auth/2.0/identifier_select'):
            raise ValueError('Invalid Steam OpenID claimed_id format')
        return v
    
    @field_validator('realm')
    @classmethod
    def validate_realm(cls, v):
        # Convert HttpUrl to string if needed
        if v is not None:
            return str(v)
        return v
    
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True
    )

class DiscordTokenResponse(BaseModel):
    """Model for Discord OAuth2 token response"""
    access_token: str
    token_type: str
    expires_in: int
    refresh_token: Optional[str] = None
    scope: str

class DiscordUserResponse(BaseModel):
    """Model for Discord user API response"""
    id: str
    username: str
    discriminator: Optional[str] = None
    avatar: Optional[str] = None
    email: Optional[str] = None
    verified: Optional[bool] = None

class SteamUserData(BaseModel):
    """Model for consolidated Steam user data from steam_utils"""
    steam_id64: str
    steam_id: str
    steam_id3: str
    steam_profile_url: str
    name: Optional[str] = None

class SteamPlayerData(BaseModel):
    """Model for Steam Web API player data response"""
    steamid: str
    personaname: str
    profileurl: str
    avatar: str
    avatarmedium: str
    avatarfull: str
    personastate: int
    communityvisibilitystate: int
    profilestate: Optional[int] = None
    lastlogoff: Optional[int] = None
    commentpermission: Optional[int] = None

class SteamPlayersResponse(BaseModel):
    """Model for Steam Web API GetPlayerSummaries response"""
    response: dict
    
    @field_validator('response')
    @classmethod
    def validate_response_structure(cls, v):
        if 'players' not in v:
            raise ValueError('Steam API response missing players array')
        return v
