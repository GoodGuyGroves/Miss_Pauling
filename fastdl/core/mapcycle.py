import json
import os
from pathlib import Path
from typing import Dict, List, Set
from .config import settings

MAPCYCLE_FILE = "mapcycle.json"

class MapcycleManager:
    """Manages mapcycle state and server mapcycle.txt files"""
    
    def __init__(self):
        self.mapcycle_path = Path(MAPCYCLE_FILE)
    
    def load_mapcycle_state(self) -> Dict[str, List[str]]:
        """Load all mapcycles from mapcycle.json"""
        if not self.mapcycle_path.exists():
            # Initialize with empty mapcycles for all configured mapcycles
            return {name: [] for name in settings.mapcycles}
        
        try:
            with open(self.mapcycle_path, 'r') as f:
                data = json.load(f)
                
                # Handle migration from old format
                if 'maps' in data:
                    # Migrate old format to new format
                    migrated_data = {name: data['maps'] for name in settings.mapcycles}
                    self.save_mapcycle_state(migrated_data)
                    return migrated_data
                
                # Ensure all configured mapcycles exist
                for name in settings.mapcycles:
                    if name not in data:
                        data[name] = []
                
                return data
        except (json.JSONDecodeError, FileNotFoundError):
            return {name: [] for name in settings.mapcycles}
    
    def save_mapcycle_state(self, mapcycles: Dict[str, List[str]]) -> None:
        """Save all mapcycles to mapcycle.json"""
        # Sort maps within each mapcycle
        sorted_mapcycles = {name: sorted(maps) for name, maps in mapcycles.items()}
        with open(self.mapcycle_path, 'w') as f:
            json.dump(sorted_mapcycles, f, indent=2)
    
    def get_map_name_without_extension(self, filename: str) -> str:
        """Strip extensions from map filename"""
        # Remove .bsp.bz2 or .bsp or .bz2
        name = filename
        if name.endswith('.bsp.bz2'):
            name = name[:-8]
        elif name.endswith('.bsp'):
            name = name[:-4]
        elif name.endswith('.bz2'):
            name = name[:-4]
        return name
    
    def update_server_mapcycles(self) -> None:
        """Update mapcycle_*.txt files for all configured servers"""
        mapcycles = self.load_mapcycle_state()
        
        for server in settings.servers:
            cfg_dir = Path(server.tf_dir) / "cfg"
            cfg_dir.mkdir(exist_ok=True)
            
            # Create a separate mapcycle file for each configured mapcycle
            for mapcycle_name, maps in mapcycles.items():
                mapcycle_file = cfg_dir / f"mapcycle_{mapcycle_name}.txt"
                
                # Write enabled maps to mapcycle_{name}.txt
                with open(mapcycle_file, 'w') as f:
                    for map_name in maps:
                        f.write(f"{map_name}\n")
    
    def toggle_map_in_mapcycle(self, filename: str, mapcycle_name: str) -> bool:
        """Toggle a map's inclusion in a specific mapcycle. Returns new state (True=enabled)"""
        if mapcycle_name not in settings.mapcycles:
            raise ValueError(f"Unknown mapcycle: {mapcycle_name}")
        
        map_name = self.get_map_name_without_extension(filename)
        mapcycles = self.load_mapcycle_state()
        
        if map_name in mapcycles[mapcycle_name]:
            mapcycles[mapcycle_name].remove(map_name)
            is_enabled = False
        else:
            mapcycles[mapcycle_name].append(map_name)
            is_enabled = True
        
        self.save_mapcycle_state(mapcycles)
        self.update_server_mapcycles()
        
        return is_enabled
    
    def is_map_in_mapcycle(self, filename: str, mapcycle_name: str) -> bool:
        """Check if a map is currently in a specific mapcycle"""
        if mapcycle_name not in settings.mapcycles:
            return False
        
        map_name = self.get_map_name_without_extension(filename)
        mapcycles = self.load_mapcycle_state()
        return map_name in mapcycles[mapcycle_name]
    
    def get_map_mapcycle_status(self, filename: str) -> Dict[str, bool]:
        """Get mapcycle status for a map across all mapcycles"""
        return {
            mapcycle_name: self.is_map_in_mapcycle(filename, mapcycle_name)
            for mapcycle_name in settings.mapcycles
        }
    
    def remove_map_from_all_mapcycles(self, filename: str) -> None:
        """Remove a map from all mapcycles"""
        map_name = self.get_map_name_without_extension(filename)
        mapcycles = self.load_mapcycle_state()
        
        # Remove from all mapcycles
        for mapcycle_name in settings.mapcycles:
            if map_name in mapcycles[mapcycle_name]:
                mapcycles[mapcycle_name].remove(map_name)
        
        self.save_mapcycle_state(mapcycles)
        self.update_server_mapcycles()

# Global instance
mapcycle_manager = MapcycleManager()