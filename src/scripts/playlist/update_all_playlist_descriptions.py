#!/usr/bin/env python3
"""
Update all owned playlist descriptions with uniform genre tags format.

This script:
1. Loads all owned playlists
2. For each playlist, collects all unique genres from artists of tracks
3. Updates the playlist description with genre tags in uniform format
4. Ensures all descriptions follow the same format

Usage:
    python src/scripts/playlist/update_all_playlist_descriptions.py
    python src/scripts/playlist/update_all_playlist_descriptions.py --dry-run  # Preview changes
"""

import argparse
from pathlib import Path

import pandas as pd
import spotipy

from src.scripts.common import (
    setup_script_environment,
    get_project_root,
    get_spotify_client,
    get_user_info,
    api_call,
    get_playlist_tracks,
)

# Setup environment
PROJECT_ROOT = setup_script_environment(__file__)

# Import sync-specific function (will be extracted later)
from src.scripts.automation.sync import _update_playlist_description_with_genres

def main():
    parser = argparse.ArgumentParser(description='Update all owned playlist descriptions with uniform genre tags')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Preview changes without updating playlists')
    parser.add_argument('--exclude-liked-songs', action='store_true',
                       help='Exclude Liked Songs playlist from updates')
    
    args = parser.parse_args()
    
    # Load data
    data_dir = PROJECT_ROOT / "data"
    print("📂 Loading data...")
    
    playlists = pd.read_parquet(data_dir / "playlists.parquet")
    
    # Filter to owned playlists only
    owned_playlists = playlists[playlists['is_owned'] == True].copy()
    
    # Exclude Liked Songs if requested
    if args.exclude_liked_songs:
        owned_playlists = owned_playlists[
            ~owned_playlists['playlist_id'].str.contains('__liked_songs__', na=False)
        ].copy()
    
    print(f"✅ Found {len(owned_playlists)} owned playlist(s) to process")
    
    if len(owned_playlists) == 0:
        print("❌ No playlists to process")
        return
    
    # Get authenticated Spotify client
    try:
        sp = get_spotify_client(__file__)
        user = get_user_info(sp)
        user_id = user["id"]
    except Exception as e:
        print(f"❌ Failed to authenticate with Spotify: {e}")
        exit(1)
    
    if args.dry_run:
        print("\n🔍 DRY RUN MODE - No changes will be made\n")
    
    # Process each playlist
    updated_count = 0
    skipped_count = 0
    error_count = 0
    
    for idx, playlist in owned_playlists.iterrows():
        playlist_id = playlist['playlist_id']
        playlist_name = playlist['name']
        
        print(f"\n📋 Processing: {playlist_name}")
        
        # Update description with genre tags (use None to fetch all tracks from playlist)
        if args.dry_run:
            # In dry run, just check what would happen
            try:
                pl = api_call(sp.playlist, playlist_id, fields="description")
                current_description = pl.get("description", "") or ""
                print(f"   Current: {current_description[:100]}..." if len(current_description) > 100 else f"   Current: {current_description}")
                print(f"   [DRY RUN] Would update description with genre tags")
            except Exception as e:
                print(f"   ✗ Failed to fetch playlist: {e}")
                error_count += 1
        else:
            try:
                if _update_playlist_description_with_genres(sp, user_id, playlist_id, None):
                    updated_count += 1
                    print(f"   ✅ Updated successfully")
                else:
                    skipped_count += 1
                    print(f"   ⏭️  No changes needed (already up to date)")
            except Exception as e:
                error_count += 1
                print(f"   ✗ Failed to update: {e}")
    
    # Summary
    print(f"\n{'='*60}")
    print(f"📊 Summary:")
    print(f"   • Processed: {len(owned_playlists)} playlist(s)")
    print(f"   • Updated: {updated_count}")
    print(f"   • Skipped: {skipped_count}")
    print(f"   • Errors: {error_count}")
    if args.dry_run:
        print(f"\n🔍 This was a DRY RUN - no changes were made")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()

