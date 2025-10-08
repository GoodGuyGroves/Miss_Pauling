import os
import json
from typing import List
from pathlib import Path
from pydantic import BaseModel
from functools import lru_cache

class Settings(BaseModel):
    """Application settings loaded from config file or environment variables"""
    api_secret_key: str = "your-secret-key-change-me-in-production"
    steam_api_key: str = "YOUR_STEAM_API_KEY"
    steam_openid_url: str = "https://steamcommunity.com/openid/login"
    realm: str = "http://localhost:8000"
    return_to: str = "http://localhost:8000/auth/steam/callback"
    frontend_url: str = "http://localhost:5173"
    allowed_origins: List[str] = ["http://localhost:5173"]
    is_using_ngrok: bool = False  # Flag to determine if we're using ngrok
    
    # Discord OAuth settings
    discord_client_id: str = ""
    discord_client_secret: str = ""
    discord_redirect_uri: str = "http://localhost:8000/auth/discord/callback"
    discord_oauth_url: str = "https://discord.com/api/oauth2/authorize"
    discord_token_url: str = "https://discord.com/api/oauth2/token"
    discord_api_url: str = "https://discord.com/api/v10"
    
    @classmethod
    def from_json(cls, file_path: str) -> "Settings":
        """Load settings from a JSON configuration file"""
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                print(f"Config file {file_path} not found, using default settings")
                return cls()
            
            with open(file_path, "r") as f:
                config_data = json.load(f)
            
            # Override with environment variables if they exist
            for field in cls.model_fields:
                env_val = os.environ.get(field.upper())
                if env_val is not None:
                    # Handle list type conversion if needed
                    if field == "allowed_origins" and isinstance(env_val, str):
                        config_data[field] = env_val.split(",")
                    else:
                        config_data[field] = env_val
                        
            # Auto-detect ngrok usage by checking if the realm contains "ngrok"
            if "realm" in config_data and "ngrok" in config_data["realm"].lower():
                config_data["is_using_ngrok"] = True
                print("Ngrok detected in URL, enabling ngrok compatibility mode")
            
            return cls(**config_data)
        except Exception as e:
            print(f"Error loading config from {file_path}: {e}")
            print("Using default settings")
            return cls()

# Use lru_cache to create a true singleton that will only be initialized once
@lru_cache
def get_settings() -> Settings:
    """
    Get application settings as a singleton.
    The LRU cache ensures this function only executes once, 
    so settings are loaded only once per application lifecycle.
    """
    config_path = Path(__file__).parent.parent / "config.json"
    return Settings.from_json(str(config_path))

# Function to get default headers for httpx requests
def get_default_headers(settings: Settings) -> dict:
    """Return default headers for httpx requests, including ngrok compatibility if needed"""
    headers = {"User-Agent": "FastAPI-Auth/1.0"}
    if settings.is_using_ngrok:
        headers["ngrok-skip-browser-warning"] = "true"
    return headers