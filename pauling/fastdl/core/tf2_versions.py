"""
TF2 Map Version Parsing and Sorting Utilities

Handles TF2 map version naming conventions:
_a# - Alpha #
_b# - Beta #
_e# - Experimental Build #
_final - Final
_rc# - Release Candidate #
_v# - Version #
"""

import re
from typing import Tuple, Optional


def parse_tf2_version(filename: str) -> Tuple[str, int, Optional[int]]:
    """
    Parse TF2 map version from filename.
    
    Returns tuple of (base_name, version_priority, version_number)
    - base_name: filename without version suffix
    - version_priority: numeric priority for sorting (higher = newer)
    - version_number: version number if present, None otherwise
    
    Priority order (low to high):
    0: alpha (_a#)
    1: experimental (_e#) 
    2: beta (_b#)
    3: release candidate (_rc#)
    4: version (_v#)
    5: final (_final)
    """
    
    # Remove .bsp extension if present
    name = filename.lower()
    if name.endswith('.bsp'):
        name = name[:-4]
    
    # Version patterns with their priorities
    patterns = [
        (r'(.+)_a(\d+)$', 0),      # alpha
        (r'(.+)_e(\d+)$', 1),      # experimental  
        (r'(.+)_b(\d+)$', 2),      # beta
        (r'(.+)_rc(\d+)$', 3),     # release candidate
        (r'(.+)_v(\d+)$', 4),      # version
        (r'(.+)_final$', 5),       # final (no number)
    ]
    
    for pattern, priority in patterns:
        match = re.match(pattern, name)
        if match:
            base_name = match.group(1)
            if priority == 5:  # _final has no number
                return (base_name, priority, None)
            else:
                version_num = int(match.group(2))
                return (base_name, priority, version_num)
    
    # No version suffix found - treat as base version (lowest priority)
    return (name, -1, None)


def tf2_sort_key(filename: str) -> Tuple[str, int, int]:
    """
    Generate sort key for TF2 map filename.
    
    Returns tuple for sorting: (base_name, version_priority, version_number)
    Maps are sorted alphabetically by base name, then by version priority, 
    then by version number.
    """
    base_name, priority, version_num = parse_tf2_version(filename)
    
    # Use 0 as default version number for comparison
    version_num = version_num if version_num is not None else 0
    
    return (base_name, priority, version_num)


def sort_tf2_maps(filenames: list) -> list:
    """
    Sort a list of TF2 map filenames according to TF2 versioning scheme.
    
    Maps are sorted alphabetically by base name, with versions ordered
    from oldest to newest within each map family.
    """
    return sorted(filenames, key=tf2_sort_key)