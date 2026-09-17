from pydantic_settings import BaseSettings, SettingsConfigDict, JsonConfigSettingsSource, PydanticBaseSettingsSource
from pydantic import HttpUrl, Field, SecretStr, BaseModel
from typing import List, Optional, Dict, Any
from functools import lru_cache
from pathlib import Path
import os
import re

# The `pauling` package directory (templates/, static/, fastdl/) and the repo root
# (settings.json, .env, docs/). All paths are resolved from here so the process can
# be started from any cwd.
PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parent
TEMPLATES_DIR = PACKAGE_DIR / "templates"
STATIC_DIR = PACKAGE_DIR / "static"
DOCS_SITE_DIR = REPO_ROOT / "docs" / "site"

# Non-secret settings file. Override to point at e.g. a Kubernetes ConfigMap mount.
SETTINGS_FILE = Path(os.environ.get("MISS_PAULING_SETTINGS_FILE", REPO_ROOT / "settings.json"))

class TF2Server(BaseModel):
    """
    TF2 server configuration for the server browser.

    The website no longer runs on the game server host, so credentials come from
    configuration rather than the server's own server.cfg. The RCON password is
    read from the environment variable TF2_RCON_PASSWORD_<NAME> (name upper-cased,
    non-alphanumerics replaced by '_'), falling back to `rcon_password` here.
    """
    name: str = Field(description="Display name for the server")
    host: str = Field(description="Server hostname or IP address")
    port: int = Field(description="Server port")
    rcon_password: Optional[str] = Field(default=None, description="RCON password (prefer the TF2_RCON_PASSWORD_<NAME> env var)")
    password_protected: bool = Field(default=False, description="Whether players need sv_password to join")

    @property
    def rcon_password_env_var(self) -> str:
        return "TF2_RCON_PASSWORD_" + re.sub(r"[^A-Za-z0-9]", "_", self.name).upper()

    def resolve_rcon_password(self) -> Optional[str]:
        return os.environ.get(self.rcon_password_env_var) or self.rcon_password

class Settings(BaseSettings):
    # Sensitive values come from the environment or <repo>/.env
    MISS_PAULING_API_SECRET_KEY: SecretStr = Field(
        description="Key used by pugs.tf for cryptographic singing and verification of auth tokens. Set it yourself."
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
    MISS_PAULING_COOKIE_DOMAIN: Optional[str] = Field(
        default=None,
        description="Domain attribute for session/CSRF cookies. Set to '.pugs.tf' in production so the login "
                    "cookie is shared between www.pugs.tf and fastdl.pugs.tf. Leave unset for localhost development."
    )

    # FastDL sub-application (fastdl/), served for the hosts listed in fastdl/settings.json
    FASTDL_ENABLED: bool = Field(
        default=True,
        description="Mount the FastDL sub-application in this process. Disable for local development "
                    "when the map directories in fastdl/settings.json don't exist."
    )
    
    # TF2 servers configuration for server browser
    TF2_SERVERS: List[TF2Server] = Field(default_factory=list)
    
    # logs.tf uploader SteamID64 for recent games
    LOGS_TF_UPLOADER_STEAM_ID: Optional[str] = Field(
        default=None,
        description="SteamID64 of the account that uploads logs to logs.tf"
    )

    environment: str = Field(
        default="development",
        description="The environment this app is running in. Use the long form of the names, eg development and production"
    )
    # Database location is read from the environment by shared/database.py
    # (MISS_PAULING_DB_URL, else MISS_PAULING_DB_PATH, else <repo>/db/sqlite.db).
    # They are declared here only so they show up in the settings documentation.
    MISS_PAULING_DB_URL: Optional[str] = Field(
        default=None,
        description="Full SQLAlchemy database URL. Takes precedence over MISS_PAULING_DB_PATH."
    )
    MISS_PAULING_DB_PATH: Optional[str] = Field(
        default=None,
        description="Path to the SQLite database file, e.g. a persistent volume mount in Kubernetes."
    )

    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True
    )

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
                json_file=SETTINGS_FILE,
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
