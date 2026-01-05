#!/usr/bin/env python3
"""
Delete all OnRepeat/Repeat playlists from Spotify library.

This script finds and deletes all playlists matching OnRepeat patterns:
- {owner}OnRepeat{year}
- {owner}RPT{year}
- {owner}Repeat{year}
- Any playlist with "OnRepeat", "RPT", or "Repeat" in the name (if owned by user)
"""

import os
import sys
import re
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
    import pandas as pd
except ImportError:
    print("ERROR: Missing required packages. Install with: pip install spotipy pandas")
    sys.exit(1)

# Load environment variables
from dotenv import load_dotenv
env_path = PROJECT_ROOT / ".env"
if env_path.exists():
    load_dotenv(env_path)

# Configuration
OWNER_NAME = os.environ.get("PLAYLIST_OWNER_NAME", "AJ")
PREFIX_REPEAT = os.environ.get("PLAYLIST_PREFIX_REPEAT", "OnRepeat")

def log(msg: str):
    """Print log message with timestamp."""
    print(msg)

def get_existing_playlists(sp: spotipy.Spotify, force_refresh: bool = False) -> dict:
    """Get all existing playlists as {name: id} dict."""
    cache_file = PROJECT_ROOT / "data" / "playlists_cache.json"
    
    if not force_refresh and cache_file.exists():
        try:
            import json
            with open(cache_file, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    
    playlists = {}
    user = sp.current_user()
    user_id = user["id"]
    
    results = sp.current_user_playlists(limit=50)
    while results:
        for item in results['items']:
            # Only include playlists owned by the user
            if item['owner']['id'] == user_id:
                playlists[item['name']] = item['id']
        
        if results['next']:
            results = sp.next(results)
        else:
            break
    
    # Cache the results
    try:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        import json
        with open(cache_file, 'w') as f:
            json.dump(playlists, f, indent=2)
    except Exception:
        pass
    
    return playlists

def find_onrepeat_playlists(playlists: dict) -> list:
    """Find all OnRepeat playlists matching various patterns."""
    onrepeat_playlists = []
    
    # Patterns to match
    patterns = [
        rf"^{OWNER_NAME}OnRepeat\d{{2,4}}$",  # AJOnRepeat25, AJOnRepeat2025
        rf"^{OWNER_NAME}RPT\d{{2,4}}$",        # AJRPT25, AJRPT2025
        rf"^{OWNER_NAME}Repeat\d{{2,4}}$",     # AJRepeat25, AJRepeat2025
        rf"^{PREFIX_REPEAT}\d{{2,4}}$",        # OnRepeat25, RPT25 (if prefix matches)
    ]
    
    # Also check for any playlist with OnRepeat/RPT/Repeat in name
    keywords = ["OnRepeat", "RPT", "Repeat", "onrepeat", "rpt", "repeat"]
    
    for name, playlist_id in playlists.items():
        # Check patterns
        for pattern in patterns:
            if re.match(pattern, name, re.IGNORECASE):
                onrepeat_playlists.append((name, playlist_id))
                break
        else:
            # Check keywords
            for keyword in keywords:
                if keyword in name:
                    onrepeat_playlists.append((name, playlist_id))
                    break
    
    return onrepeat_playlists

def main():
    """Main function."""
    log("=" * 60)
    log("🗑️  Delete OnRepeat Playlists")
    log("=" * 60)
    
    # Authenticate
    try:
        scope = "playlist-modify-public playlist-modify-private"
        sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope))
        user = sp.current_user()
        log(f"✅ Authenticated as: {user['display_name']} ({user['id']})")
    except Exception as e:
        log(f"❌ Authentication failed: {e}")
        log("   Make sure SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET, and SPOTIPY_REDIRECT_URI are set in .env")
        return False
    
    # Get all playlists
    log("\n📋 Loading playlists...")
    playlists = get_existing_playlists(sp, force_refresh=True)
    log(f"   Found {len(playlists)} owned playlists")
    
    # Find OnRepeat playlists
    log("\n🔍 Searching for OnRepeat playlists...")
    onrepeat = find_onrepeat_playlists(playlists)
    
    if not onrepeat:
        log("   ✅ No OnRepeat playlists found")
        return True
    
    log(f"   Found {len(onrepeat)} OnRepeat playlist(s):")
    for name, _ in onrepeat:
        log(f"      • {name}")
    
    # Confirm deletion
    log(f"\n⚠️  About to delete {len(onrepeat)} playlist(s)")
    response = input("   Continue? (yes/no): ").strip().lower()
    if response not in ['yes', 'y']:
        log("   ❌ Cancelled")
        return False
    
    # Delete playlists
    log("\n🗑️  Deleting playlists...")
    user_id = user["id"]
    deleted = 0
    failed = 0
    
    for name, playlist_id in onrepeat:
        try:
            sp.user_playlist_unfollow(user_id, playlist_id)
            log(f"   ✅ Deleted: {name}")
            deleted += 1
        except Exception as e:
            log(f"   ❌ Failed to delete '{name}': {e}")
            failed += 1
    
    log(f"\n📊 Summary:")
    log(f"   ✅ Deleted: {deleted}")
    if failed > 0:
        log(f"   ❌ Failed: {failed}")
    
    # Invalidate cache
    cache_file = PROJECT_ROOT / "data" / "playlists_cache.json"
    if cache_file.exists():
        cache_file.unlink(missing_ok=True)
        log("   🗑️  Cleared playlist cache")
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        log("\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        log(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

