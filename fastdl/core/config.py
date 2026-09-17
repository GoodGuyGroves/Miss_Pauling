from pydantic import BaseModel, field_validator, HttpUrl
from typing import List
from pathlib import Path
import json
import os
from functools import lru_cache

# The FastDL package directory. Config and state files live here regardless of
# the working directory the website process is started from.
FASTDL_DIR = Path(__file__).resolve().parent.parent
# Override to point at e.g. a Kubernetes ConfigMap mount
SETTINGS_FILE = Path(os.environ.get("FASTDL_SETTINGS_FILE", FASTDL_DIR / "settings.json"))


class Settings(BaseModel):
    # Hostnames that route to the FastDL sub-application (e.g. fastdl.pugs.tf).
    # Requests for any other host fall through to the main website routes.
    hosts: List[str]
    # Directory the map files are stored in and served from. Created if missing.
    maps_dir: str
    allowed_map_extensions: List[str]
    max_map_file_size: int
    mapcycles: List[str]
    # Where mapcycle membership is persisted. Point at a persistent volume in Kubernetes.
    mapcycle_state_file: str = str(FASTDL_DIR / "mapcycle.json")
    website_base_url: HttpUrl = HttpUrl("http://localhost:8000")

    @field_validator('maps_dir')
    @classmethod
    def validate_maps_dir(cls, v: str) -> str:
        v = v.rstrip('/')
        Path(v).mkdir(parents=True, exist_ok=True)
        return v

    @field_validator('website_base_url', mode='before')
    @classmethod
    def validate_website_base_url(cls, v):
        # Remove trailing slash before HttpUrl validation
        if isinstance(v, str):
            return v.rstrip('/')
        return v


def load_settings() -> Settings:
    """Load FastDL settings from fastdl/settings.json"""
    with open(SETTINGS_FILE, 'r') as f:
        data = json.load(f)
    return Settings(**data)


@lru_cache()
def get_settings() -> Settings:
    return load_settings()


settings = get_settings()
