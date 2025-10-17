"""TF2 server query service using RCON"""

import asyncio
import re
from pathlib import Path
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import logging

try:
    from rcon.source import Client as RCONClient
except ImportError:
    RCONClient = None

from website.app.core.config import TF2Server, settings

logger = logging.getLogger(__name__)


class PlayerInfo(BaseModel):
    """Individual player information"""
    name: str
    user_id: int
    steam_id: str
    time_connected: str
    ping: int
    loss: int
    state: str
    team: Optional[str] = None
    player_class: Optional[str] = None
    score: Optional[int] = None
    kills: Optional[int] = None
    deaths: Optional[int] = None
    assists: Optional[int] = None


class TournamentInfo(BaseModel):
    """Tournament mode information"""
    enabled: bool = False
    round_state: Optional[str] = None
    red_score: Optional[int] = None
    blue_score: Optional[int] = None
    time_remaining: Optional[str] = None
    win_limit: Optional[int] = None
    time_limit: Optional[int] = None


class ServerStatus(BaseModel):
    """Server status information"""
    name: str
    host: str
    port: int
    map: str
    players: int
    max_players: int
    connect_url: str
    status: str = Field(description="online, offline, or error")
    response_time_ms: Optional[int] = None
    password_protected: bool = False
    tournament_info: Optional[TournamentInfo] = None
    player_list: List[PlayerInfo] = Field(default_factory=list)
    spectators: Optional[int] = None


class TF2Service:
    """Service for querying TF2 servers via RCON"""
    
    def __init__(self):
        self.servers = settings.TF2_SERVERS
    
    def _parse_server_cfg(self, server_dir: str) -> Dict[str, str]:
        """Parse server.cfg file to extract rcon_password and sv_password"""
        cfg_path = Path(server_dir) / "tf" / "cfg" / "server.cfg"
        config = {}
        
        if not cfg_path.exists():
            logger.warning(f"Server config not found: {cfg_path}")
            return config
            
        try:
            with open(cfg_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('//') or not line:
                        continue
                    
                    # Match patterns like: rcon_password "value" or sv_password "value"
                    if 'rcon_password' in line:
                        match = re.search(r'rcon_password\s+"([^"]*)"', line)
                        if match:
                            config['rcon_password'] = match.group(1)
                    
                    if 'sv_password' in line:
                        match = re.search(r'sv_password\s+"([^"]*)"', line)
                        if match:
                            config['sv_password'] = match.group(1)
                            
        except Exception as e:
            logger.error(f"Error parsing server config {cfg_path}: {e}")
            
        return config
    
    async def _query_server_rcon(self, server: TF2Server, rcon_password: str) -> Optional[Dict[str, Any]]:
        """Query a single server via RCON"""
        if not RCONClient:
            logger.error("RCON client not available - install 'rcon' package")
            return None
            
        try:
            # Use asyncio to run RCON query with timeout
            loop = asyncio.get_event_loop()
            
            def _rcon_query():
                with RCONClient(server.host, server.port, passwd=rcon_password, timeout=5) as client:
                    # Get server status and additional info
                    status_output = client.run('status')
                    
                    # Get tournament mode info
                    mp_tournament = client.run('mp_tournament')
                    mp_winlimit = client.run('mp_winlimit') 
                    mp_timelimit = client.run('mp_timelimit')
                    
                    # Get max players setting
                    maxplayers = ""
                    try:
                        maxplayers = client.run('maxplayers')
                    except:
                        pass
                    
                    # Get SourceTV info for spectator count
                    tv_status = ""
                    try:
                        tv_status = client.run('tv_status')
                    except:
                        pass  # TV might not be enabled
                    
                    return {
                        'status': status_output,
                        'mp_tournament': mp_tournament,
                        'mp_winlimit': mp_winlimit,
                        'mp_timelimit': mp_timelimit,
                        'maxplayers': maxplayers,
                        'tv_status': tv_status
                    }
            
            # Run RCON query in thread pool to avoid blocking
            rcon_data = await asyncio.wait_for(
                loop.run_in_executor(None, _rcon_query),
                timeout=10.0
            )
            
            return self._parse_rcon_output(rcon_data)
            
        except asyncio.TimeoutError:
            logger.warning(f"RCON timeout for {server.host}:{server.port}")
            return None
        except Exception as e:
            logger.error(f"RCON error for {server.host}:{server.port}: {e}")
            return None
    
    def _parse_rcon_output(self, rcon_data: Dict[str, str]) -> Dict[str, Any]:
        """Parse all RCON command outputs"""
        result = {
            'map': 'unknown',
            'players': 0,
            'max_players': 0,
            'server_name': 'Unknown Server',
            'player_list': [],
            'tournament_info': {},
            'spectators': 0
        }
        
        try:
            # Parse main status output
            status_output = rcon_data.get('status', '')
            lines = status_output.split('\n')
            
            # Debug: Log the status output
            logger.info(f"Status output received: {len(lines)} lines")
            logger.debug(f"Full status output:\n{status_output}")
            
            parsing_players = False
            for line in lines:
                line = line.strip()
                
                # Parse hostname line: hostname: Server Name
                if line.startswith('hostname:'):
                    result['server_name'] = line.split(':', 1)[1].strip()
                
                # Parse map line: map     : cp_badlands at: 0 x, 0 y, 0 z
                if line.startswith('map'):
                    map_match = re.search(r'map\s*:\s*(\S+)', line)
                    if map_match:
                        result['map'] = map_match.group(1)
                
                # Parse players line: players : 2 (24 max)
                if 'players' in line and 'max' in line:
                    player_match = re.search(r'players\s*:\s*(\d+)\s*\(\s*(\d+)\s*max\)', line)
                    if player_match:
                        result['players'] = int(player_match.group(1))
                        result['max_players'] = int(player_match.group(2))
                
                # Detect start of player list (more flexible patterns)
                if ('userid' in line and 'name' in line) or ('# ' in line and 'connected' in line):
                    parsing_players = True
                    logger.debug(f"Started parsing players at line: {line}")
                    continue
                
                # Parse individual player lines
                if parsing_players and line and line.startswith('#'):
                    # More flexible regex for different status output formats
                    # Example formats:
                    # # 2 "Player Name" STEAM_0:1:12345 00:01:23 154 0 active
                    # #  2 "Player Name"  STEAM_0:1:12345  00:01:23   154    0 active
                    
                    # Extract components step by step for better debugging
                    try:
                        # Split by quotes to get the name easily
                        if '"' in line:
                            # Format: # userid "name" steamid time ping loss state
                            parts = line.split('"')
                            if len(parts) >= 3:
                                pre_name = parts[0].strip()  # "# userid"
                                name = parts[1]  # player name
                                post_name = parts[2].strip()  # steamid time ping loss state
                                
                                # Extract userid from pre_name
                                userid_match = re.search(r'#\s*(\d+)', pre_name)
                                if userid_match:
                                    user_id = int(userid_match.group(1))
                                else:
                                    continue
                                
                                # Extract steam ID, time, ping, loss, state from post_name
                                # Split by whitespace and filter empty strings
                                post_parts = [p for p in post_name.split() if p]
                                logger.debug(f"Parsing player line post_parts: {post_parts}")
                                
                                if len(post_parts) >= 4:
                                    # Find Steam ID in various formats
                                    steam_id = "Unknown"
                                    for part in post_parts:
                                        if (part.startswith('STEAM_') or 
                                            part.startswith('[U:') or 
                                            part.startswith('BOT') or
                                            'steam' in part.lower()):
                                            steam_id = part
                                            break
                                    
                                    # Find time (format like 01:23:45 or 00:05:12)
                                    time_connected = "00:00:00"
                                    for part in post_parts:
                                        # Time format: digits:digits:digits, not starting with STEAM_ or [
                                        if (':' in part and 
                                            not part.startswith('STEAM_') and 
                                            not part.startswith('[') and
                                            len(part.split(':')) >= 2):
                                            # Verify it looks like time (numbers separated by colons)
                                            time_parts = part.split(':')
                                            if all(p.isdigit() for p in time_parts):
                                                time_connected = part
                                                break
                                    
                                    # Find ping and loss (consecutive numeric values)
                                    ping = 0
                                    loss = 0
                                    for i, part in enumerate(post_parts):
                                        if part.isdigit() and i + 1 < len(post_parts) and post_parts[i + 1].isdigit():
                                            ping = int(part)
                                            loss = int(post_parts[i + 1])
                                            break
                                    
                                    # State is usually the last part or contains specific keywords
                                    state = "unknown"
                                    for part in post_parts:
                                        if part in ['active', 'spawning', 'connecting', 'disconnected']:
                                            state = part
                                            break
                                    if state == "unknown" and post_parts:
                                        state = post_parts[-1]  # Last part as fallback
                                    
                                    player_info = {
                                        'name': name,
                                        'user_id': user_id,
                                        'steam_id': steam_id,
                                        'time_connected': time_connected,
                                        'ping': ping,
                                        'loss': loss,
                                        'state': state
                                    }
                                    result['player_list'].append(player_info)
                                    logger.debug(f"Parsed player: {player_info}")
                    except Exception as e:
                        logger.debug(f"Error parsing player line '{line}': {e}")
                        continue
            
            # Parse tournament info
            mp_tournament = rcon_data.get('mp_tournament', '')
            tournament_enabled = '1' in mp_tournament or 'true' in mp_tournament.lower()
            
            result['tournament_info'] = {
                'enabled': tournament_enabled,
                'win_limit': self._extract_cvar_value(rcon_data.get('mp_winlimit', '')),
                'time_limit': self._extract_cvar_value(rcon_data.get('mp_timelimit', ''))
            }
            
            # Parse maxplayers cvar
            maxplayers_value = self._extract_cvar_value(rcon_data.get('maxplayers', ''))
            if maxplayers_value:
                result['maxplayers_value'] = maxplayers_value
            
            # Parse SourceTV status for spectator count
            tv_status = rcon_data.get('tv_status', '')
            spectator_match = re.search(r'(\d+)\s+spectators?', tv_status)
            if spectator_match:
                result['spectators'] = int(spectator_match.group(1))
            
            # Debug: Final summary
            logger.info(f"Parsed {len(result['player_list'])} players, tournament: {result['tournament_info']}")
                        
        except Exception as e:
            logger.error(f"Error parsing RCON output: {e}")
            
        return result
    
    def _extract_cvar_value(self, cvar_output: str) -> Optional[int]:
        """Extract numeric value from cvar output like 'mp_timelimit = 30'"""
        try:
            # Look for pattern like 'cvar_name = value'
            match = re.search(r'=\s*(\d+)', cvar_output)
            if match:
                return int(match.group(1))
        except:
            pass
        return None
    
    async def get_server_status(self, server: TF2Server) -> ServerStatus:
        """Get status for a single server"""
        import time
        start_time = time.time()
        
        # Parse server config for passwords
        config = self._parse_server_cfg(server.dir)
        rcon_password = config.get('rcon_password')
        sv_password = config.get('sv_password', '')
        
        if not rcon_password:
            logger.warning(f"No RCON password found for {server.name}")
            return ServerStatus(
                name=server.name,
                host=server.host,
                port=server.port,
                map="unknown",
                players=0,
                max_players=0,
                connect_url=f"steam://connect/{server.host}:{server.port}",
                status="error",
                password_protected=bool(sv_password)
            )
        
        # Query server via RCON
        server_data = await self._query_server_rcon(server, rcon_password)
        response_time = int((time.time() - start_time) * 1000)
        
        if server_data is None:
            return ServerStatus(
                name=server.name,
                host=server.host,
                port=server.port,
                map="unknown",
                players=0,
                max_players=0,
                connect_url=f"steam://connect/{server.host}:{server.port}",
                status="offline",
                response_time_ms=response_time,
                password_protected=bool(sv_password)
            )
        
        # Build connect URL with password if needed
        connect_url = f"steam://connect/{server.host}:{server.port}"
        if sv_password:
            connect_url += f"/{sv_password}"
        
        # Build tournament info
        tournament_data = server_data.get('tournament_info', {})
        tournament_info = None
        if tournament_data.get('enabled'):
            tournament_info = TournamentInfo(
                enabled=True,
                win_limit=tournament_data.get('win_limit'),
                time_limit=tournament_data.get('time_limit')
            )
        
        # Build player list
        player_list = []
        for player_data in server_data.get('player_list', []):
            player_list.append(PlayerInfo(
                name=player_data['name'],
                user_id=player_data['user_id'],
                steam_id=player_data['steam_id'],
                time_connected=player_data['time_connected'],
                ping=player_data['ping'],
                loss=player_data['loss'],
                state=player_data['state']
            ))
        
        # Use actual player list count if RCON count seems wrong
        rcon_player_count = server_data.get('players', 0)
        actual_player_count = len(player_list)
        player_count = actual_player_count if actual_player_count > rcon_player_count else rcon_player_count
        
        # For max_players, try multiple sources
        max_players = server_data.get('max_players', 0)
        if max_players == 0:
            # Try to get from maxplayers cvar
            maxplayers_cvar = server_data.get('maxplayers_value', 0)
            if maxplayers_cvar > 0:
                max_players = maxplayers_cvar
            else:
                max_players = 24  # Common TF2 server default
        
        return ServerStatus(
            name=server_data.get('server_name', server.name),
            host=server.host,
            port=server.port,
            map=server_data.get('map', 'unknown'),
            players=player_count,
            max_players=max_players,
            connect_url=connect_url,
            status="online",
            response_time_ms=response_time,
            password_protected=bool(sv_password),
            tournament_info=tournament_info,
            player_list=player_list,
            spectators=server_data.get('spectators', 0)
        )
    
    async def get_all_servers_status(self) -> List[ServerStatus]:
        """Get status for all configured servers"""
        if not self.servers:
            return []
        
        # Query all servers concurrently
        tasks = [self.get_server_status(server) for server in self.servers]
        return await asyncio.gather(*tasks)


# Create singleton instance
tf2_service = TF2Service()