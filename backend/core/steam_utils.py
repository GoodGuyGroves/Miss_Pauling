"""
Utility functions for working with Steam IDs and API
"""
import re
import httpx
from datetime import datetime, timezone
from typing import Dict, Optional, Any
from app.core.config import get_settings, get_default_headers

# Get settings for API calls
settings = get_settings()

# Constants for Steam ID conversion
STEAM_ID_BASE = 76561197960265728

def convert_steamid(steamid64: str) -> Dict[str, str]:
    """Convert Steam ID64 to other formats"""
    steamid64_int = int(steamid64)
    
    # Calculate SteamID
    y = 0 if (steamid64_int % 2 == 0) else 1
    steamid = f"STEAM_0:{y}:{(steamid64_int - STEAM_ID_BASE - y) // 2}"
    
    # Calculate SteamID3
    steamid3 = f"[U:1:{steamid64_int - STEAM_ID_BASE}]"
    
    # Generate profile URL
    profile_url = f"https://steamcommunity.com/profiles/{steamid64}"
    
    return {
        "steam_id64": steamid64,
        "steam_id": steamid,
        "steam_id3": steamid3,
        "steam_profile_url": profile_url
    }

def validate_steamid(steamid: str) -> Optional[str]:
    """Validate and normalize Steam ID to Steam ID64"""
    # Steam ID64 (17 digits)
    if re.match(r'^\d{17}$', steamid):
        return steamid
        
    # SteamID format (STEAM_0:X:XXXXXXXX)
    elif re.match(r'^STEAM_0:[01]:\d+$', steamid):
        parts = steamid.split(':')
        y = int(parts[1])
        z = int(parts[2])
        steamid64 = z * 2 + STEAM_ID_BASE + y
        return str(steamid64)
        
    # SteamID3 format ([U:1:XXXXXXX])
    elif re.match(r'^\[U:1:\d+\]$', steamid):
        account_id = int(re.search(r'\[U:1:(\d+)\]', steamid).group(1))
        steamid64 = account_id + STEAM_ID_BASE
        return str(steamid64)
    
    # Steam profile URL
    elif 'steamcommunity.com/profiles/' in steamid:
        match = re.search(r'steamcommunity\.com/profiles/(\d{17})', steamid)
        if match:
            return match.group(1)
            
    # Steam vanity URL
    elif 'steamcommunity.com/id/' in steamid:
        match = re.search(r'steamcommunity\.com/id/([^/]+)', steamid)
        if match:
            vanity_url = match.group(1)
            return resolve_vanity_url(vanity_url)
    
    return None

async def resolve_vanity_url(vanity_url: str) -> Optional[str]:
    """Resolve Steam vanity URL to Steam ID64"""
    api_key = settings.STEAM_API_KEY
    url = f"https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/?key={api_key}&vanityurl={vanity_url}"
    
    try:
        headers = get_default_headers(settings)
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            data = response.json()
            
            if data['response']['success'] == 1:
                return data['response']['steamid']
    except Exception as e:
        print(f"Error resolving vanity URL: {e}")
    
    return None

async def get_steam_user_data(steam_id64: str) -> Dict[str, Any]:
    """
    Get Steam user data from Steam Web API, including:
    - Username
    - Profile URL 
    - Different Steam ID formats
    """
    # Initialize with the Steam ID formats regardless of API success
    steam_ids = convert_steamid(steam_id64)
    user_data = {
        "steam_id64": steam_id64,
        "steam_id": steam_ids["steam_id"],
        "steam_id3": steam_ids["steam_id3"],
        "steam_profile_url": steam_ids["steam_profile_url"]
    }
    
    # Only fetch additional data if API key is configured
    if settings.steam_api_key and settings.steam_api_key != "YOUR_STEAM_API_KEY":
        api_key = settings.steam_api_key
        url = f"https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/?key={api_key}&steamids={steam_id64}"
        
        try:
            headers = get_default_headers(settings)
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers)
                data = response.json()
                
                if 'response' in data and 'players' in data['response'] and len(data['response']['players']) > 0:
                    player = data['response']['players'][0]
                    
                    # Update user data with key fields we care about
                    user_data.update({
                        "name": player.get("personaname"),
                        # Use the profile URL from the API if available, otherwise use our generated one
                        "steam_profile_url": player.get("profileurl", user_data["steam_profile_url"])
                    })
                    
        except Exception as e:
            print(f"Error getting Steam user details: {e}")
    
    return user_data