#!/usr/bin/env python3
"""Delete incorrectly named genre, top, discovery, and vibes playlists."""

import sys
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

from scripts.sync import (
    get_spotify_client, get_existing_playlists, log, api_call,
    PREFIX_GENRE_MONTHLY, PREFIX_MOST_PLAYED, PREFIX_DISCOVERY, 
    PREFIX_TIME_BASED, PREFIX_REPEAT, OWNER_NAME, _invalidate_playlist_cache
)

def is_incorrectly_named(name):
    """Check if playlist name is incorrectly formatted."""
    # Check for template placeholders (definitely wrong)
    if any(p in name for p in ["{mon}", "{year}", "{prefix}", "{genre}", "{owner}"]):
        return True, "Contains template placeholders"
    
    # Genre playlists
    genres = ["HipHop", "Dance", "Other"]
    for genre in genres:
        if name.startswith(genre):
            # Correct yearly: HipHopFinds25
            # Correct monthly: HipHopFindsDec25
            yearly_correct = re.match(rf"^{genre}Finds\d{{2}}$", name)
            monthly_correct = re.match(rf"^{genre}Finds(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\d{{2}}$", name)
            
            if not yearly_correct and not monthly_correct:
                # Check if it's close but wrong
                if name.startswith(f"{genre}Finds"):
                    return True, f"Genre playlist with wrong format"
                elif name.startswith(genre):
                    return True, f"Genre playlist missing prefix or wrong format"
    
    # Top playlists
    if "Top" in name or name.startswith(f"{OWNER_NAME}Top"):
        # Correct: AJTop25
        correct = re.match(rf"^{OWNER_NAME}Top\d{{2}}$", name)
        if not correct and name.startswith(f"{OWNER_NAME}Top"):
            return True, "Top playlist with wrong format"
    
    # Discovery playlists
    if "Discovery" in name or "Dscvr" in name or name.startswith(f"{OWNER_NAME}Discovery") or name.startswith(f"{OWNER_NAME}Dscvr"):
        # Correct: AJDiscovery25 or AJDscvr25
        correct = re.match(rf"^{OWNER_NAME}(Discovery|Dscvr)\d{{2}}$", name)
        if not correct and (name.startswith(f"{OWNER_NAME}Discovery") or name.startswith(f"{OWNER_NAME}Dscvr")):
            return True, "Discovery playlist with wrong format"
    
    # Vibes playlists
    if "Vibes" in name or "VBZ" in name or name.startswith(f"{OWNER_NAME}Vibes") or name.startswith(f"{OWNER_NAME}VBZ"):
        # Correct: AJVibes25 or AJVBZ25
        correct = re.match(rf"^{OWNER_NAME}(Vibes|VBZ)\d{{2}}$", name)
        if not correct and (name.startswith(f"{OWNER_NAME}Vibes") or name.startswith(f"{OWNER_NAME}VBZ")):
            return True, "Vibes playlist with wrong format"
    
    # OnRepeat playlists
    if "OnRepeat" in name or "RPT" in name or "Repeat" in name or name.startswith(f"{OWNER_NAME}OnRepeat") or name.startswith(f"{OWNER_NAME}RPT"):
        # Correct: AJOnRepeat25 or AJRPT25
        correct = re.match(rf"^{OWNER_NAME}(OnRepeat|RPT)\d{{2}}$", name)
        if not correct and (name.startswith(f"{OWNER_NAME}OnRepeat") or name.startswith(f"{OWNER_NAME}RPT")):
            return True, "OnRepeat playlist with wrong format"
    
    return False, None

def get_user_info(sp):
    """Get current user info."""
    return api_call(sp.current_user)

if __name__ == "__main__":
    log("=" * 60)
    log("Delete Incorrectly Named Playlists")
    log("=" * 60)
    
    try:
        sp = get_spotify_client()
        user = get_user_info(sp)
        user_id = user["id"]
        existing = get_existing_playlists(sp, force_refresh=True)
        
        if not existing:
            log("  ℹ️  No playlists found")
            sys.exit(0)
        
        log(f"  Checking {len(existing)} playlist(s)...")
        
        incorrect_playlists = []
        for name, playlist_id in existing.items():
            is_incorrect, reason = is_incorrectly_named(name)
            if is_incorrect:
                incorrect_playlists.append((name, playlist_id, reason))
        
        if not incorrect_playlists:
            log("  ℹ️  No incorrectly named playlists found")
            sys.exit(0)
        
        log(f"\n  Found {len(incorrect_playlists)} incorrectly named playlist(s):")
        for name, playlist_id, reason in incorrect_playlists:
            log(f"    - '{name}' ({reason})")
        
        log(f"\n  🗑️  Deleting {len(incorrect_playlists)} playlist(s)...")
        
        deleted_count = 0
        for name, playlist_id, reason in incorrect_playlists:
            try:
                api_call(sp.user_playlist_unfollow, user_id, playlist_id)
                log(f"     ✅ Deleted: '{name}'")
                deleted_count += 1
                # Invalidate cache after each deletion
                _invalidate_playlist_cache()
            except Exception as e:
                log(f"     ⚠️  Failed to delete '{name}': {e}")
        
        log(f"\n  ✅ Deleted {deleted_count} incorrectly named playlist(s)")
        
        log("\n" + "=" * 60)
        log("✅ Complete!")
        log("=" * 60)
    except Exception as e:
        log(f"ERROR: {e}")
        import traceback
        log(traceback.format_exc())
        sys.exit(1)

