from pydantic import BaseModel, field_validator, HttpUrl
from typing import List
import json
import os
from functools import lru_cache

class ServerConfig(BaseModel):
    name: str
    tf_dir: str
    
    @field_validator('tf_dir')
    @classmethod
    def validate_tf_dir(cls, v: str) -> str:
        v = v.rstrip('/')
        if not os.path.exists(v):
            raise ValueError(f"tf_dir path does not exist: {v}")
        if not os.path.isdir(v):
            raise ValueError(f"tf_dir path is not a directory: {v}")
        return v

class Settings(BaseModel):
    servers: List[ServerConfig]
    maps_dir: str
    allowed_map_extensions: List[str]
    max_map_file_size: int
    mapcycles: List[str]
    cors_origins: List[str]
    cors_methods: List[str]
    cors_headers: List[str]
    allowed_hosts: List[str]
    website_base_url: HttpUrl = HttpUrl("http://localhost:8000")
    
    @field_validator('maps_dir')
    @classmethod
    def validate_maps_dir(cls, v: str) -> str:
        v = v.rstrip('/')
        if not os.path.exists(v):
            raise ValueError(f"maps_dir path does not exist: {v}")
        if not os.path.isdir(v):
            raise ValueError(f"maps_dir path is not a directory: {v}")
        return v
    
    @field_validator('website_base_url', mode='before')
    @classmethod
    def validate_website_base_url(cls, v):
        # Remove trailing slash before HttpUrl validation
        if isinstance(v, str):
            return v.rstrip('/')
        return v

def load_settings() -> Settings:
    """Load server settings"""
    with open('settings.json', 'r') as f:
        data = json.load(f)
    return Settings(**data)

@lru_cache()
def get_settings() -> Settings:
    return load_settings()

settings = get_settings()
