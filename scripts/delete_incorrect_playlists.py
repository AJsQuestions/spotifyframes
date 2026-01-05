#!/usr/bin/env python3
"""Quick script to delete incorrectly named yearly genre playlists."""

import sys
import re
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Load environment variables from .env file if available
try:
    from dotenv import load_dotenv
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

# Import after path setup
from scripts.sync import (
    get_spotify_client, get_existing_playlists, log, api_call,
    PREFIX_GENRE_MONTHLY, OWNER_NAME
)

def find_incorrectly_named_playlists(sp):
    """Find playlists that were incorrectly named using the monthly template for yearly playlists."""
    log("=" * 60)
    log("Finding Incorrectly Named Yearly Genre Playlists")
    log("=" * 60)
    
    existing = get_existing_playlists(sp, force_refresh=True)
    user = get_user_info(sp)
    user_id = user["id"]
    
    if not existing:
        log("  ℹ️  No playlists found")
        return
    
    # Patterns for incorrectly named playlists
    # Correct yearly format: HipHopFinds25, DanceFinds25, OtherFinds25
    # Incorrect might have: template placeholders, wrong structure, etc.
    genres = ["HipHop", "Dance", "Other"]
    prefix = PREFIX_GENRE_MONTHLY
    
    incorrect_playlists = []
    
    for name, playlist_id in existing.items():
        # Check if it's a genre playlist
        for genre in genres:
            if name.startswith(genre):
                # Check for template placeholders (definitely wrong)
                if any(placeholder in name for placeholder in ["{mon}", "{year}", "{prefix}", "{genre}", "{owner}"]):
                    incorrect_playlists.append((name, playlist_id, f"Contains template placeholders"))
                    continue
                
                # Check if it matches monthly pattern but should be yearly
                # Monthly: HipHopFindsDec25, DanceFindsNov25, etc.
                # Yearly: HipHopFinds25, DanceFinds25, etc.
                month_pattern = r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\d{2}$"
                if re.search(month_pattern, name):
                    # This is a monthly playlist, not yearly - skip
                    continue
                
                # Check if it looks like it should be yearly but has wrong format
                # Should be: GenrePrefix + 2-digit year (e.g., HipHopFinds25)
                expected_prefix = f"{genre}{prefix}"
                if name.startswith(expected_prefix):
                    suffix = name[len(expected_prefix):]
                    # If suffix doesn't match expected 2-digit year pattern, might be wrong
                    if not (suffix.isdigit() and len(suffix) == 2):
                        # Could be wrong - but be conservative, only flag obvious issues
                        if len(suffix) > 3 or not suffix[-2:].isdigit():
                            incorrect_playlists.append((name, playlist_id, f"Unexpected suffix format: '{suffix}'"))
    
    if not incorrect_playlists:
        log("  ℹ️  No incorrectly named playlists found")
        return
    
    log(f"\n  Found {len(incorrect_playlists)} potentially incorrect playlist(s):")
    for name, playlist_id, reason in incorrect_playlists:
        log(f"    - '{name}' ({reason})")
    
    # Ask for confirmation (but since user wants fast, we'll delete them)
    log(f"\n  🗑️  Deleting {len(incorrect_playlists)} playlist(s)...")
    
    deleted_count = 0
    for name, playlist_id, reason in incorrect_playlists:
        try:
            api_call(sp.user_playlist_unfollow, user_id, playlist_id)
            log(f"     ✅ Deleted: '{name}'")
            deleted_count += 1
        except Exception as e:
            log(f"     ⚠️  Failed to delete '{name}': {e}")
    
    log(f"\n  ✅ Deleted {deleted_count} incorrectly named playlist(s)")

def get_user_info(sp):
    """Get current user info."""
    return api_call(sp.current_user)

if __name__ == "__main__":
    try:
        sp = get_spotify_client()
        find_incorrectly_named_playlists(sp)
        log("\n" + "=" * 60)
        log("✅ Complete!")
        log("=" * 60)
    except Exception as e:
        log(f"ERROR: {e}")
        import traceback
        log(traceback.format_exc())
        sys.exit(1)

