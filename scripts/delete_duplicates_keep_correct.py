#!/usr/bin/env python3
"""Delete duplicate playlists, keeping the correctly named one."""

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
    get_spotify_client, get_existing_playlists, get_playlist_tracks,
    log, api_call, PREFIX_GENRE_MONTHLY, OWNER_NAME
)

def is_correctly_named(name):
    """Check if playlist name follows correct patterns."""
    # Correct yearly genre format: HipHopFinds25, DanceFinds25, OtherFinds25
    # Correct monthly format: HipHopFindsDec25, DanceFindsNov25, etc.
    # Correct master format: AJamHip-Hop, AJamElectronic, etc.
    
    # Check for template placeholders (definitely wrong)
    if any(p in name for p in ["{mon}", "{year}", "{prefix}", "{genre}", "{owner}"]):
        return False
    
    # Yearly genre: GenrePrefix + 2-digit year
    yearly_pattern = r"^(HipHop|Dance|Other)Finds\d{2}$"
    if re.match(yearly_pattern, name):
        return True
    
    # Monthly genre: GenrePrefix + Month + 2-digit year
    monthly_pattern = r"^(HipHop|Dance|Other)Finds(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\d{2}$"
    if re.match(monthly_pattern, name):
        return True
    
    # Master genre: OwnerPrefix + Genre
    if name.startswith(f"{OWNER_NAME}am") and len(name) > len(f"{OWNER_NAME}am"):
        return True
    
    # Regular monthly: OwnerPrefix + Month + Year
    regular_monthly = rf"^{OWNER_NAME}Finds(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\d{{2}}$"
    if re.match(regular_monthly, name):
        return True
    
    # Regular yearly: OwnerPrefix + Year
    regular_yearly = rf"^{OWNER_NAME}Finds\d{{2}}$"
    if re.match(regular_yearly, name):
        return True
    
    # Other patterns (Top, Vibes, etc.)
    other_patterns = [
        rf"^{OWNER_NAME}Top\d{{2}}$",
        rf"^{OWNER_NAME}Vibes\d{{2}}$",
        rf"^{OWNER_NAME}OnRepeat\d{{2}}$",
        rf"^{OWNER_NAME}Discovery\d{{2}}$",
    ]
    if any(re.match(p, name) for p in other_patterns):
        return True
    
    # If it doesn't match known patterns but doesn't have placeholders, 
    # assume it might be correct (user-created playlists)
    return True

def get_user_info(sp):
    """Get current user info."""
    return api_call(sp.current_user)

if __name__ == "__main__":
    log("=" * 60)
    log("Delete Duplicate Playlists (Keep Correctly Named)")
    log("=" * 60)
    
    try:
        sp = get_spotify_client()
        user = get_user_info(sp)
        user_id = user["id"]
        existing = get_existing_playlists(sp, force_refresh=True)
        
        if not existing:
            log("  ℹ️  No playlists found")
            sys.exit(0)
        
        log(f"  Checking {len(existing)} playlist(s) for duplicates...")
        
        # Build track sets
        playlist_track_sets = {}
        checked = 0
        for name, playlist_id in existing.items():
            try:
                tracks = get_playlist_tracks(sp, playlist_id, force_refresh=False)
                track_set = frozenset(tracks)
                if track_set in playlist_track_sets:
                    playlist_track_sets[track_set].append((name, playlist_id))
                else:
                    playlist_track_sets[track_set] = [(name, playlist_id)]
                checked += 1
                if checked % 100 == 0:
                    log(f"  Progress: {checked}/{len(existing)}...")
            except Exception as e:
                log(f"  ⚠️  Could not read '{name}': {e}")
                continue
        
        # Find duplicates and delete incorrectly named ones
        deleted_count = 0
        for track_set, playlists in playlist_track_sets.items():
            if len(playlists) > 1 and len(track_set) > 0:
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

