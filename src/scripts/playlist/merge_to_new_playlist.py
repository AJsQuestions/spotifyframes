#!/usr/bin/env python3
"""
Merge two playlists into the older playlist, removing duplicates.

This script:
1. Finds two playlists by name
2. Determines which playlist is older (by earliest track added_at timestamp)
3. Renames the older playlist to the specified name
4. Gets all tracks from both playlists
5. Adds unique tracks from the newer playlist to the older (renamed) playlist
6. Optionally deletes the newer playlist

Usage:
    python scripts/merge_to_new_playlist.py "Playlist1" "Playlist2" "New Playlist Name"
    python scripts/merge_to_new_playlist.py --playlist1 "Playlist1" --playlist2 "Playlist2" --new-name "New Playlist Name"
    python scripts/merge_to_new_playlist.py --playlist1 "Playlist1" --playlist2 "Playlist2" --new-name "New Playlist Name" --keep-newer
"""

import argparse
import os
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
    chunked,
    find_playlist_by_name,
    get_playlist_earliest_timestamp,
)

# Setup environment
PROJECT_ROOT = setup_script_environment(__file__)

def merge_to_new_playlist(sp: spotipy.Spotify, playlist1_name: str, playlist2_name: str, new_playlist_name: str, delete_newer: bool = True) -> None:
    """Merge two playlists into the older playlist, renaming it to the new name."""
    # Get user info once
    user = get_user_info(sp)
    user_id = user["id"]
    
    # Load playlist data
    data_dir = PROJECT_ROOT / "data"
    playlists_df = pd.read_parquet(data_dir / "playlists.parquet")
    
    # Check if new playlist name already exists
    existing_names = set(playlists_df['name'].tolist())
    if new_playlist_name in existing_names:
        raise ValueError(f"Playlist '{new_playlist_name}' already exists! Please choose a different name.")
    
    # Find playlists
    try:
        pl1 = find_playlist_by_name(playlists_df, playlist1_name)
        pl2 = find_playlist_by_name(playlists_df, playlist2_name)
    except ValueError as e:
        print(f"❌ Error: {e}")
        return
    
    pl1_id = pl1['playlist_id']
    pl2_id = pl2['playlist_id']
    pl1_track_count = pl1['track_count']
    pl2_track_count = pl2['track_count']
    
    # Determine which playlist is older by checking earliest added_at timestamp
    playlist_tracks_path = data_dir / "playlist_tracks.parquet"
    if playlist_tracks_path.exists():
        try:
            playlist_tracks_df = pd.read_parquet(playlist_tracks_path)
            if 'added_at' in playlist_tracks_df.columns:
                pl1_earliest = get_playlist_earliest_timestamp(playlist_tracks_df, pl1_id)
                pl2_earliest = get_playlist_earliest_timestamp(playlist_tracks_df, pl2_id)
            else:
                # No added_at column, use playlist order as fallback (first playlist is older)
                print("⚠️  No 'added_at' column in playlist_tracks.parquet, using playlist order.")
                pl1_earliest = pd.Timestamp.min
                pl2_earliest = pd.Timestamp.max
        except Exception as e:
            print(f"⚠️  Error reading playlist_tracks.parquet: {e}. Using playlist order.")
            pl1_earliest = pd.Timestamp.min
            pl2_earliest = pd.Timestamp.max
    else:
        # No playlist_tracks file, use playlist order as fallback
        print("⚠️  playlist_tracks.parquet not found. Using playlist order to determine older playlist.")
        pl1_earliest = pd.Timestamp.min
        pl2_earliest = pd.Timestamp.max
    
    # Older playlist becomes the source (target)
    if pl1_earliest <= pl2_earliest:
        older_pl = pl1
        older_id = pl1_id
        older_name = playlist1_name
        newer_pl = pl2
        newer_id = pl2_id
        newer_name = playlist2_name
    else:
        older_pl = pl2
        older_id = pl2_id
        older_name = playlist2_name
        newer_pl = pl1
        newer_id = pl1_id
        newer_name = playlist1_name
    
    print(f"📦 Older playlist (source): {older_name} (ID: {older_id}, {older_pl['track_count']} tracks)")
    print(f"📦 Newer playlist: {newer_name} (ID: {newer_id}, {newer_pl['track_count']} tracks)")
    print(f"✨ New name: {new_playlist_name}")
    
    # Get tracks from both playlists
    print(f"\n📥 Fetching tracks from {older_name}...")
    older_tracks = get_playlist_tracks(sp, older_id, force_refresh=True)
    print(f"   Found {len(older_tracks)} tracks")
    
    print(f"📥 Fetching tracks from {newer_name}...")
    newer_tracks = get_playlist_tracks(sp, newer_id, force_refresh=True)
    print(f"   Found {len(newer_tracks)} tracks")
    
    # Find tracks in newer playlist that aren't in older playlist
    tracks_to_add = newer_tracks - older_tracks
    duplicates = newer_tracks & older_tracks
    
    print(f"\n📊 Analysis:")
    print(f"   • Tracks in older playlist: {len(older_tracks)}")
    print(f"   • Tracks in newer playlist: {len(newer_tracks)}")
    print(f"   • Duplicates (will be skipped): {len(duplicates)}")
    print(f"   • Unique tracks to add: {len(tracks_to_add)}")
    
    if not tracks_to_add and len(older_tracks) == len(newer_tracks | older_tracks):
        print(f"\n✅ No new tracks to add! Newer playlist is a subset of older playlist.")
        if delete_newer:
            print(f"\n🗑️  Deleting newer playlist '{newer_name}'...")
            try:
                api_call(sp.user_playlist_unfollow, user_id, newer_id)
                print(f"   ✓ Deleted: {newer_name}")
            except Exception as e:
                print(f"   ✗ Failed to delete {newer_name}: {e}")
        
        # Still rename the older playlist
        if older_name != new_playlist_name:
            print(f"\n✏️  Renaming '{older_name}' to '{new_playlist_name}'...")
            try:
                api_call(sp.user_playlist_change_details, user_id, older_id, name=new_playlist_name)
                print(f"   ✓ Renamed: '{older_name}' -> '{new_playlist_name}'")
            except Exception as e:
                print(f"   ✗ Failed to rename: {e}")
                raise
        
        print(f"\n✅ Merge complete!")
        print(f"   • Renamed '{older_name}' to '{new_playlist_name}'")
        return
    
    # Rename the older playlist
    if older_name != new_playlist_name:
        print(f"\n✏️  Renaming '{older_name}' to '{new_playlist_name}'...")
        try:
            api_call(sp.user_playlist_change_details, user_id, older_id, name=new_playlist_name)
            print(f"   ✓ Renamed: '{older_name}' -> '{new_playlist_name}'")
        except Exception as e:
            print(f"   ✗ Failed to rename: {e}")
            raise
    
    # Add tracks from newer playlist to older playlist
    if tracks_to_add:
        print(f"\n➕ Adding {len(tracks_to_add)} unique tracks to '{new_playlist_name}'...")
        tracks_list = list(tracks_to_add)
        
        chunk_count = 0
        for chunk in chunked(tracks_list, 50):  # Spotify API limit is 100, using 50 to be safe
            chunk_count += 1
            print(f"   Adding chunk {chunk_count} ({len(chunk)} tracks)...")
            try:
                api_call(sp.playlist_add_items, older_id, chunk)
            except Exception as e:
                print(f"   ✗ Failed to add chunk {chunk_count}: {e}")
                raise
        
        print(f"   ✓ Successfully added {len(tracks_to_add)} tracks")
    
    # Verify all tracks are preserved before deletion
    if delete_newer:
        print(f"\n🔍 Verifying all tracks are preserved in target playlist...")
        final_older_tracks = get_playlist_tracks(sp, older_id, force_refresh=True)
        missing_tracks = newer_tracks - final_older_tracks
        
        if missing_tracks:
            print(f"   ⚠️  WARNING: {len(missing_tracks)} tracks from '{newer_name}' are NOT in target playlist!")
            print(f"   💾 Creating backup before deletion...")
            from src.scripts.automation.data_protection import safe_delete_playlist
            success, backup_file = safe_delete_playlist(
                sp, newer_id, newer_name,
                create_backup=True,
                verify_tracks_preserved_in=older_id
            )
            if not success:
                print(f"   ❌ Deletion aborted - tracks not verified in target playlist")
                if backup_file:
                    print(f"   💾 Backup created: {backup_file.name}")
        else:
            print(f"   ✅ All tracks verified in target playlist")
            from src.scripts.automation.data_protection import safe_delete_playlist
            success, backup_file = safe_delete_playlist(
                sp, newer_id, newer_name,
                create_backup=True,
                verify_tracks_preserved_in=older_id
            )
            if success:
                print(f"   ✓ Deleted: {newer_name}")
            else:
                print(f"   ⚠️  Deletion failed or aborted")
                if backup_file:
                    print(f"   💾 Backup created: {backup_file.name}")
    
    # Final verification
    final_tracks = get_playlist_tracks(sp, older_id, force_refresh=True)
    expected_tracks = older_tracks | newer_tracks
    
    print(f"\n✅ Merge complete!")
    print(f"   • Renamed '{older_name}' to '{new_playlist_name}'")
    print(f"   • Final track count: {len(final_tracks)}")
    print(f"   • Added {len(tracks_to_add)} unique tracks")
    print(f"   • Removed {len(duplicates)} duplicates")
    
    # Verify no data loss
    if final_tracks != expected_tracks:
        missing = expected_tracks - final_tracks
        if missing:
            print(f"   ⚠️  WARNING: {len(missing)} tracks missing from final playlist!")
            print(f"   Missing tracks: {list(missing)[:10]}")
    
    # Optionally trigger incremental sync (controlled by environment variable)
    if os.environ.get("AUTO_SYNC_AFTER_WRITE", "false").lower() in ("true", "1", "yes"):
        print(f"\n🔄 Triggering incremental sync...")
        try:
            from src.scripts.common import trigger_incremental_sync
            trigger_incremental_sync(quiet=False)
        except Exception as e:
            print(f"   ⚠️  Sync failed (non-fatal): {e}")

def main():
    parser = argparse.ArgumentParser(description='Merge two playlists into the older playlist, renaming it to the new name')
    parser.add_argument('playlists', nargs='*', help='Playlist1, Playlist2, and New Playlist Name (in order)')
    parser.add_argument('--playlist1', help='First playlist name')
    parser.add_argument('--playlist2', help='Second playlist name')
    parser.add_argument('--new-name', help='Name for the merged playlist (older playlist will be renamed to this)')
    parser.add_argument('--keep-newer', action='store_true', help='Keep newer playlist after merge (default: delete)')
    
    args = parser.parse_args()
    
    # Determine playlists and new name
    if args.playlist1 and args.playlist2 and args.new_name:
        playlist1_name = args.playlist1
        playlist2_name = args.playlist2
        new_playlist_name = args.new_name
    elif len(args.playlists) == 3:
        playlist1_name = args.playlists[0]
        playlist2_name = args.playlists[1]
        new_playlist_name = args.playlists[2]
    else:
        parser.print_help()
        exit(1)
    
    # Get authenticated Spotify client
    try:
        sp = get_spotify_client(__file__)
    except Exception as e:
        print(f"❌ Failed to authenticate with Spotify: {e}")
        exit(1)
    
    # Merge playlists
    merge_to_new_playlist(sp, playlist1_name, playlist2_name, new_playlist_name, delete_newer=not args.keep_newer)

if __name__ == "__main__":
    main()

