from pydantic_settings import BaseSettings, SettingsConfigDict, JsonConfigSettingsSource, PydanticBaseSettingsSource
from pydantic import HttpUrl, Field, SecretStr, model_validator
from typing import List, Optional
from functools import lru_cache

class Settings(BaseSettings):
    # Load sensitive values from .env
    MISS_PAULING_API_SECRET_KEY: SecretStr = Field(
        description="Key used by Miss Pauling for cryptographic singing and verification of auth tokens. Set it yourself."
    )
    STEAM_API_KEY: SecretStr = Field(
        description="Steam API key for Steam OpenID integration"
    )
    DISCORD_CLIENT_SECRET: SecretStr = Field(
        description="Discord applications OAth2 client secret"
    )
    DISCORD_TOKEN: SecretStr = Field(
        description="The Discord applications secret token"
    )

    # Load values from settings.json
    STEAM_OPENID_URL: HttpUrl = Field(
        default=HttpUrl("https://steamcommunity.com/openid/login"),
        description="Steam's OpenID URL"
    )
    STEAM_OPENID_REALM: HttpUrl = Field(
        default=HttpUrl("http://localhost:8000"),
        description="The realm to provide to OpenID. Used by Steam to determine which domain/application is requesting auth and also used for constructing auth URLs. Should match the applications base URL",
    )
    STEAM_OPENID_CALLBACK_URL: HttpUrl = Field(
        default=HttpUrl("http://localhost:8000/auth/steam/callback"),
        description="The callback URL for Steam's OpenID to return to after a user authenticates"
    )

    DISCORD_APPLICATION_ID: str = Field(
        description="The Discord applications OAuth2 Client ID"
    )
    DISCORD_PUBLIC_KEY: str = Field(
        description="The Discord applications OAuth2 public key (found under general information page)"
    )
    DISCORD_CALLBACK_URL: HttpUrl = Field(
        default=HttpUrl("http://localhost:8000/auth/discord/callback"),
        description="Discord OAuth callback URL"
    )
    DISCORD_OAUTH_URL: HttpUrl = Field(
        default=HttpUrl("https://discord.com/api/oauth2/authorize"),
        description="Discord OAuth authorization endpoint"
    )
    DISCORD_TOKEN_URL: HttpUrl = Field(
        default=HttpUrl("https://discord.com/api/oauth2/token"),
        description="Discord OAuth token exchange endpoint"
    )
    DISCORD_API_URL: HttpUrl = Field(
        default=HttpUrl("https://discord.com/api/v10"),
        description="Discord API base URL"
    )

    MISS_PAULING_CORS_ORIGINS: List[str] = Field(default=["*"])
    MISS_PAULING_CORS_HEADERS: List[str] = Field(default=["*"])
    MISS_PAULING_CORS_METHODS: List[str] = Field(default=["GET", "POST"])
    MISS_PAULING_CORS_CREDENTIALS: bool = Field(default=True)
    
    MISS_PAULING_SESSION_EXPIRY_HOURS: int = 24 * 7  # 1 week

    environment: str = Field(
        default="development",
        description="The environment this app is running in. Use the long form of the names, eg development and production"
    )
    MISS_PAULING_DB_TYPE: str = Field(
        default="sqlite",
        description="The type of DB to use. Defaults to sqlite."
    )
    MISS_PAULING_DB_PATH: Optional[str] = Field(
        default="../db/sqlite.db",
        description="Path to SQLite database file (required when MISS_PAULING_DB_TYPE is 'sqlite')"
    )
    MISS_PAULING_DB_URL: Optional[str] = Field(
        default=None,
        description="The URL to the chosen database (required when MISS_PAULING_DB_TYPE is 'postgresql')"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True
    )

    @model_validator(mode='after')
    def validate_db_config(self):
        """Validate database configuration based on DB type"""
        db_type = self.MISS_PAULING_DB_TYPE.lower()
        
        if db_type == "sqlite":
            if not self.MISS_PAULING_DB_PATH:
                raise ValueError("MISS_PAULING_DB_PATH is required when MISS_PAULING_DB_TYPE is 'sqlite'")
            # Generate SQLite URL from path
            self.MISS_PAULING_DB_URL = f"sqlite:///{self.MISS_PAULING_DB_PATH}"
        elif db_type == "postgresql":
            if not self.MISS_PAULING_DB_URL:
                raise ValueError("MISS_PAULING_DB_URL is required when MISS_PAULING_DB_TYPE is 'postgresql'")
        else:
            raise ValueError(f"Unsupported database type: {db_type}. Supported types are 'sqlite' and 'postgresql'")
        
        return self

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            JsonConfigSettingsSource(
                settings_cls, 
                json_file='settings.json', 
                json_file_encoding='utf-8'
            ),
            file_secret_settings,
        )


# Use lru_cache to create a true singleton that will only be initialized once
@lru_cache()
def get_settings() -> Settings:
    return Settings()  # pyright: ignore[reportCallIssue]

# Function to get default headers for httpx requests
def get_default_headers(settings: Settings) -> dict:
    """Return default headers for httpx requests"""
    headers = {"User-Agent": "FastAPI-Auth/1.0"}
    return headers

settings = get_settings()
