"""
Playlist Rename Helper Functions

Extracted from sync.py to improve code organization.
Handles playlist renaming and prefix migration.
"""

import spotipy
from typing import Dict, Set
from src.scripts.automation.error_handling import handle_errors
from src.scripts.common.api_wrapper import api_call as standard_api_call
from src.scripts.automation.config import (
    PREFIX_MONTHLY, PREFIX_MOST_PLAYED, PREFIX_DISCOVERY
)


def build_prefix_mapping() -> Dict[str, str]:
    """
    Build mapping of old prefixes to new prefixes.
    
    Returns:
        Dictionary mapping old prefix to new prefix
    """
    old_to_new = {}
    
    # Check "Auto" -> monthly prefix
    if PREFIX_MONTHLY != "Auto" and PREFIX_MONTHLY != "auto":
        old_to_new["Auto"] = PREFIX_MONTHLY
        old_to_new["auto"] = PREFIX_MONTHLY.lower()
        old_to_new["AUTO"] = PREFIX_MONTHLY.upper()
    
    # Check other prefixes if they changed
    if PREFIX_MOST_PLAYED != "Top":
        old_to_new["Top"] = PREFIX_MOST_PLAYED
    
    if PREFIX_DISCOVERY not in ["Discover", "Discovery", "Dscvr"]:
        old_to_new["Discover"] = PREFIX_DISCOVERY
        old_to_new["Discovery"] = PREFIX_DISCOVERY
    
    return old_to_new


def rename_playlist_with_prefix(
    sp: spotipy.Spotify,
    user_id: str,
    playlist_id: str,
    old_name: str,
    old_to_new: Dict[str, str]
) -> bool:
    """
    Rename a single playlist if it uses an old prefix.
    
    Args:
        sp: Spotify client
        user_id: User ID
        playlist_id: Playlist ID
        old_name: Current playlist name
        old_to_new: Mapping of old prefixes to new prefixes
    
    Returns:
        True if playlist was renamed, False otherwise
    """
    for old_prefix, new_prefix in old_to_new.items():
        if old_prefix in old_name:
            new_name = old_name.replace(old_prefix, new_prefix)
            if new_name != old_name:
                try:
                    standard_api_call(
                        sp.playlist_change_details,
                        playlist_id,
                        name=new_name,
                        verbose=False
                    )
                    return True
                except Exception:
                    # Skip if rename fails (playlist might not exist or permission issue)
                    return False
    return False
