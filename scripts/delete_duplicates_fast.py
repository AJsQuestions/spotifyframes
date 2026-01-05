#!/usr/bin/env python3
"""Fast duplicate playlist deletion - only checks playlists with similar names."""

import sys
import re
from pathlib import Path
from collections import defaultdict

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
    get_spotify_client, get_existing_playlists, get_playlist_tracks,
    log, api_call, _invalidate_playlist_cache, OWNER_NAME
)

def is_correctly_named(name):
    """Quick check if playlist name follows correct patterns."""
    # Check for template placeholders (definitely wrong)
    if any(p in name for p in ["{mon}", "{year}", "{prefix}", "{genre}", "{owner}"]):
        return False
    
    # Common patterns - if it matches known good patterns, it's likely correct
    patterns = [
        rf"^{OWNER_NAME}Finds(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\d{{2}}$",  # Monthly
        rf"^{OWNER_NAME}Finds\d{{2}}$",  # Yearly
        rf"^(HipHop|Dance|Other)Finds\d{{2}}$",  # Yearly genre
        rf"^(HipHop|Dance|Other)Finds(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\d{{2}}$",  # Monthly genre
        rf"^{OWNER_NAME}(Top|Vibes|VBZ|OnRepeat|RPT|Discovery|Dscvr)\d{{2}}$",  # Yearly special
        rf"^{OWNER_NAME}am[A-Z]",  # Master genre
    ]
    
    return any(re.match(p, name) for p in patterns)

def get_user_info(sp):
    """Get current user info."""
    return api_call(sp.current_user)

if __name__ == "__main__":
    log("=" * 60)
    log("Fast Duplicate Playlist Deletion")
    log("=" * 60)
    
    try:
        sp = get_spotify_client()
        user = get_user_info(sp)
        user_id = user["id"]
        existing = get_existing_playlists(sp, force_refresh=True)
        
        if not existing:
            log("  ℹ️  No playlists found")
            sys.exit(0)
        
        log(f"  Found {len(existing)} playlist(s)")
        log("  Checking for likely duplicates (similar names)...")
        
        # Group playlists by base name (without year/month variations)
        # This quickly identifies likely duplicates
        name_groups = defaultdict(list)
        for name, playlist_id in existing.items():
            # Extract base name (remove year/month suffixes)
            base = re.sub(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\d{2}$', '', name)
            base = re.sub(r'\d{2,4}$', '', base)
            if base:
                name_groups[base].append((name, playlist_id))
        
        # Check groups with multiple playlists (likely duplicates)
        potential_duplicates = []
        for base, playlists in name_groups.items():
            if len(playlists) > 1:
                # Check if they have same tracks
                track_sets = {}
                for name, playlist_id in playlists:
                    try:
                        tracks = get_playlist_tracks(sp, playlist_id, force_refresh=False)
                        track_set = frozenset(tracks)
                        if track_set in track_sets:
                            track_sets[track_set].append((name, playlist_id))
                        else:
                            track_sets[track_set] = [(name, playlist_id)]
                    except Exception as e:
                        log(f"  ⚠️  Could not read '{name}': {e}")
                        continue
                
                # Find actual duplicates (same tracks)
                for track_set, dup_playlists in track_sets.items():
                    if len(dup_playlists) > 1 and len(track_set) > 0:
                        potential_duplicates.append((track_set, dup_playlists))
        
        if not potential_duplicates:
            log("  ℹ️  No duplicate playlists found")
            sys.exit(0)
        
        # Delete duplicates, keeping correctly named ones
        deleted_count = 0
        for track_set, playlists in potential_duplicates:
            # Sort by correctness (correct first), then alphabetically
            playlists_sorted = sorted(
                playlists,
                key=lambda x: (not is_correctly_named(x[0]), x[0])
            )
            
            keep_playlist = playlists_sorted[0]
            duplicates = playlists_sorted[1:]
            
            # Only delete if we're keeping a correctly named one
            if is_correctly_named(keep_playlist[0]):
                log(f"\n  🔍 {len(playlists)} duplicate(s) with {len(track_set)} tracks:")
                log(f"     ✅ Keeping: '{keep_playlist[0]}'")
                
                for dup_name, dup_id in duplicates:
                    try:
                        api_call(sp.user_playlist_unfollow, user_id, dup_id)
                        log(f"     🗑️  Deleted: '{dup_name}'")
                        deleted_count += 1
                        _invalidate_playlist_cache()
                    except Exception as e:
                        log(f"     ⚠️  Failed to delete '{dup_name}': {e}")
        
        if deleted_count > 0:
            log(f"\n  ✅ Deleted {deleted_count} duplicate playlist(s)")
        else:
            log("  ℹ️  No duplicate playlists found")
        
        log("\n" + "=" * 60)
        log("✅ Complete!")
        log("=" * 60)
    except Exception as e:
        log(f"ERROR: {e}")
        import traceback
        log(traceback.format_exc())
        sys.exit(1)

