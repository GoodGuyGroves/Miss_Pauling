"""logs.tf API service for retrieving recent game logs"""

import asyncio
import httpx
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import logging

from website.app.core.config import settings

logger = logging.getLogger(__name__)


class GameLog(BaseModel):
    """Individual game log information"""
    log_id: int
    title: str
    map: str
    format: str
    date: datetime
    more_tf_url: str
    logs_tf_url: str
    duration: Optional[int] = None  # seconds
    
    @classmethod
    def from_logs_tf_response(cls, log_data: Dict[str, Any]) -> "GameLog":
        """Create GameLog from logs.tf API response"""
        log_id = log_data.get('id', 0)
        
        # Parse date from timestamp
        date = datetime.now(timezone.utc)
        if 'date' in log_data:
            try:
                date = datetime.fromtimestamp(log_data['date'], tz=timezone.utc)
            except (ValueError, TypeError):
                logger.warning(f"Invalid date in log {log_id}: {log_data.get('date')}")
        
        # Determine format from title or players
        format_str = "Unknown"
        title = log_data.get('title', '')
        players = log_data.get('players', 0)
        
        # Try to determine format from common patterns
        if 'hl' in title.lower() or 'highlander' in title.lower():
            format_str = "Highlander"
        elif '6v6' in title or '6s' in title.lower() or 'sixes' in title.lower():
            format_str = "6v6"
        elif '4v4' in title or 'fours' in title.lower():
            format_str = "4v4"
        elif 'dm' in title.lower() or 'deathmatch' in title.lower():
            format_str = "DM"
        elif 'mge' in title.lower():
            format_str = "MGE"
        elif 'pub' in title.lower() or 'casual' in title.lower():
            format_str = "Pub"
        elif players:
            # Guess from player count
            if players >= 16:
                format_str = "Highlander"
            elif players >= 10:
                format_str = "6v6"
            elif players >= 6:
                format_str = "4v4"
            else:
                format_str = f"{players}p"
        
        return cls(
            log_id=log_id,
            title=title,
            map=log_data.get('map', 'Unknown'),
            format=format_str,
            date=date,
            more_tf_url=f"https://more.tf/log/{log_id}",
            logs_tf_url=f"https://logs.tf/{log_id}",
            duration=log_data.get('duration')
        )


class LogsService:
    """Service for querying logs.tf API"""
    
    BASE_URL = "https://logs.tf/api/v1"
    CACHE_DURATION = timedelta(minutes=5)  # Cache for 5 minutes
    
    def __init__(self):
        self.uploader_steam_id = settings.LOGS_TF_UPLOADER_STEAM_ID
        self._cache: Optional[List[GameLog]] = None
        self._cache_time: Optional[datetime] = None
        
    async def get_recent_games(self, limit: int = 10) -> List[GameLog]:
        """Get recent games from logs.tf"""
        if not self.uploader_steam_id:
            logger.warning("No LOGS_TF_UPLOADER_STEAM_ID configured")
            return []
        
        # Check cache first
        now = datetime.now(timezone.utc)
        if (self._cache is not None and 
            self._cache_time is not None and 
            now - self._cache_time < self.CACHE_DURATION):
            logger.debug("Returning cached recent games")
            return self._cache[:limit]
        
        try:
            url = f"{self.BASE_URL}/log"
            params = {
                'uploader': self.uploader_steam_id,
                'limit': limit
            }
            logger.info(f"Requesting logs.tf API: {url} with params: {params}")
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                
                data = response.json()
                logs_data = data.get('logs', [])
                
                game_logs = []
                for log_data in logs_data:
                    try:
                        game_log = GameLog.from_logs_tf_response(log_data)
                        game_logs.append(game_log)
                    except Exception as e:
                        logger.error(f"Error parsing log {log_data.get('id', 'unknown')}: {e}")
                        continue
                
                # Update cache
                self._cache = game_logs
                self._cache_time = now
                
                logger.info(f"Retrieved {len(game_logs)} recent games from logs.tf")
                return game_logs[:limit]
                
        except httpx.TimeoutException:
            logger.warning("Timeout querying logs.tf API")
            return []
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error querying logs.tf API: {e.response.status_code} - {e.response.text}")
            return []
        except Exception as e:
            logger.error(f"Error querying logs.tf API: {e}")
            return []


# Create singleton instance
logs_service = LogsService()