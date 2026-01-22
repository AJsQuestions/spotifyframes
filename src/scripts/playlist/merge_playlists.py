#!/usr/bin/env python3
"""
Merge two playlists, removing duplicates.

This script:
1. Finds two playlists by name
2. Determines which playlist is older (by earliest track added_at timestamp)
3. Uses the older playlist as the target
4. Gets all tracks from both playlists
5. Adds unique tracks from newer playlist to older (target) playlist
6. Optionally deletes the newer playlist

Usage:
    python scripts/merge_playlists.py "Playlist1" "Playlist2"
    python scripts/merge_playlists.py --playlist1 "Playlist1" --playlist2 "Playlist2"
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

def merge_playlists(sp: spotipy.Spotify, playlist1_name: str, playlist2_name: str, delete_newer: bool = True) -> None:
    """Merge two playlists into the older playlist, removing duplicates."""
    # Get user info once
    user = get_user_info(sp)
    user_id = user["id"]
    
    # Load playlist data
    data_dir = PROJECT_ROOT / "data"
    playlists_df = pd.read_parquet(data_dir / "playlists.parquet")
    
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
    
    # Older playlist becomes the target
    if pl1_earliest <= pl2_earliest:
        target_pl = pl1
        target_id = pl1_id
        target_name = playlist1_name
        source_pl = pl2
        source_id = pl2_id
        source_name = playlist2_name
    else:
        target_pl = pl2
        target_id = pl2_id
        target_name = playlist2_name
        source_pl = pl1
        source_id = pl1_id
        source_name = playlist1_name
    
    print(f"🎯 Target playlist (older): {target_name} (ID: {target_id}, {target_pl['track_count']} tracks)")
    print(f"📦 Source playlist (newer): {source_name} (ID: {source_id}, {source_pl['track_count']} tracks)")
    
    # Get tracks from both playlists
    print(f"\n📥 Fetching tracks from {target_name}...")
    target_tracks = get_playlist_tracks(sp, target_id, force_refresh=True)
    print(f"   Found {len(target_tracks)} tracks")
    
    print(f"📥 Fetching tracks from {source_name}...")
    source_tracks = get_playlist_tracks(sp, source_id, force_refresh=True)
    print(f"   Found {len(source_tracks)} tracks")
    
    # Find tracks in source that aren't in target
    tracks_to_add = source_tracks - target_tracks
    duplicates = source_tracks & target_tracks
    
    print(f"\n📊 Analysis:")
    print(f"   • Tracks in target: {len(target_tracks)}")
    print(f"   • Tracks in source: {len(source_tracks)}")
    print(f"   • Duplicates (will be skipped): {len(duplicates)}")
    print(f"   • Unique tracks to add: {len(tracks_to_add)}")
    
    if not tracks_to_add:
        print(f"\n✅ No new tracks to add! Source playlist is a subset of target playlist.")
        if delete_newer:
            print(f"\n🗑️  Deleting source playlist '{source_name}'...")
            try:
                api_call(sp.user_playlist_unfollow, user_id, source_id)
                print(f"   ✓ Deleted: {source_name}")
            except Exception as e:
                print(f"   ✗ Failed to delete {source_name}: {e}")
        return
    
    # Add tracks to target playlist
    print(f"\n➕ Adding {len(tracks_to_add)} unique tracks to '{target_name}'...")
    tracks_list = list(tracks_to_add)
    
    chunk_count = 0
    for chunk in chunked(tracks_list, 50):  # Spotify API limit is 100, using 50 to be safe
        chunk_count += 1
        print(f"   Adding chunk {chunk_count} ({len(chunk)} tracks)...")
        try:
            api_call(sp.playlist_add_items, target_id, chunk)
        except Exception as e:
            print(f"   ✗ Failed to add chunk {chunk_count}: {e}")
            raise
    
    print(f"   ✓ Successfully added {len(tracks_to_add)} tracks")
    
    # Verify all tracks are preserved before deletion
    if delete_newer:
        print(f"\n🔍 Verifying all tracks are preserved in target playlist...")
        final_target_tracks = get_playlist_tracks(sp, target_id, force_refresh=True)
        missing_tracks = source_tracks - final_target_tracks
        
        if missing_tracks:
            print(f"   ⚠️  WARNING: {len(missing_tracks)} tracks from '{source_name}' are NOT in target playlist!")
            print(f"   💾 Creating backup before deletion...")
            from src.scripts.automation.data_protection import safe_delete_playlist
            success, backup_file = safe_delete_playlist(
                sp, source_id, source_name,
                create_backup=True,
                verify_tracks_preserved_in=target_id
            )
            if not success:
                print(f"   ❌ Deletion aborted - tracks not verified in target playlist")
                if backup_file:
                    print(f"   💾 Backup created: {backup_file.name}")
                return
        else:
            print(f"   ✅ All tracks verified in target playlist")
            print(f"\n🗑️  Deleting source playlist '{source_name}'...")
            from src.scripts.automation.data_protection import safe_delete_playlist
            success, backup_file = safe_delete_playlist(
                sp, source_id, source_name,
                create_backup=True,
                verify_tracks_preserved_in=target_id
            )
            if success:
                print(f"   ✓ Deleted: {source_name}")
            else:
                print(f"   ⚠️  Deletion failed or aborted")
                if backup_file:
                    print(f"   💾 Backup created: {backup_file.name}")
    
    # Final verification
    final_target_tracks = get_playlist_tracks(sp, target_id, force_refresh=True)
    print(f"\n✅ Merge complete!")
    print(f"   • '{target_name}' now contains {len(final_target_tracks)} tracks")
    print(f"   • Added {len(tracks_to_add)} unique tracks")
    print(f"   • Removed {len(duplicates)} duplicates")
    
    # Verify no data loss
    expected_tracks = target_tracks | source_tracks
    if final_target_tracks != expected_tracks:
        missing = expected_tracks - final_target_tracks
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
    parser = argparse.ArgumentParser(description='Merge two playlists into the older playlist, removing duplicates')
    parser.add_argument('playlists', nargs='*', help='Two playlist names (order doesn\'t matter - older will be used as target)')
    parser.add_argument('--playlist1', help='First playlist name')
    parser.add_argument('--playlist2', help='Second playlist name')
    parser.add_argument('--keep-newer', action='store_true', help='Keep newer playlist after merge (default: delete)')
    
    args = parser.parse_args()
    
    # Determine playlists
    if args.playlist1 and args.playlist2:
        playlist1_name = args.playlist1
        playlist2_name = args.playlist2
    elif len(args.playlists) == 2:
        playlist1_name = args.playlists[0]
        playlist2_name = args.playlists[1]
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
    merge_playlists(sp, playlist1_name, playlist2_name, delete_newer=not args.keep_newer)

if __name__ == "__main__":
    main()

