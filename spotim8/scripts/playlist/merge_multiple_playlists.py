#!/usr/bin/env python3
"""
Merge multiple playlists into one, removing duplicates.

This script:
1. Finds multiple playlists by name
2. Determines which playlist is oldest (by earliest track added_at timestamp)
3. Uses the older playlist as the source
4. Renames it to the specified name
5. Merges all other playlists into it
6. Optionally deletes the other playlists

Usage:
    python scripts/merge_multiple_playlists.py "New Playlist Name" "Playlist1" "Playlist2" "Playlist3" ...
    python scripts/merge_multiple_playlists.py --new-name "New Playlist Name" --playlists "Playlist1" "Playlist2" "Playlist3"
"""

import argparse
from pathlib import Path

import pandas as pd
import spotipy

from spotim8.scripts.common import (
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

def merge_multiple_playlists(sp: spotipy.Spotify, playlist_names: list[str], new_playlist_name: str, delete_others: bool = True) -> None:
    """Merge multiple playlists into the oldest one, renaming it to the new name."""
    # Get user info once
    user = get_user_info(sp)
    user_id = user["id"]
    
    # Load playlist data
    data_dir = PROJECT_ROOT / "data"
    playlists_df = pd.read_parquet(data_dir / "playlists.parquet")
    
    # Deduplicate by playlist_id in case there are duplicate rows
    playlists_df = playlists_df.drop_duplicates(subset=['playlist_id'])
    
    # Check if new playlist name already exists
    existing_names = set(playlists_df['name'].tolist())
    if new_playlist_name in existing_names:
        raise ValueError(f"Playlist '{new_playlist_name}' already exists! Please choose a different name.")
    
    if len(playlist_names) < 2:
        raise ValueError("At least 2 playlists are required for merging.")
    
    # Find all playlists
    playlists = []
    for name in playlist_names:
        try:
            pl = find_playlist_by_name(playlists_df, name)
            playlists.append((name, pl))
        except ValueError as e:
            print(f"❌ Error: {e}")
            return
    
    if len(playlists) < 2:
        print("❌ Error: Need at least 2 valid playlists to merge")
        return
    
    print(f"📦 Found {len(playlists)} playlist(s) to merge:")
    for name, pl in playlists:
        print(f"   • {name} ({pl['track_count']} tracks)")
    print(f"✨ Target name: {new_playlist_name}")
    
    # Determine which playlist is oldest by checking earliest added_at timestamp
    playlist_tracks_path = data_dir / "playlist_tracks.parquet"
    earliest_timestamps = {}
    
    if playlist_tracks_path.exists():
        try:
            playlist_tracks_df = pd.read_parquet(playlist_tracks_path)
            if 'added_at' in playlist_tracks_df.columns:
                for name, pl in playlists:
                    pl_id = pl['playlist_id']
                    earliest_timestamps[pl_id] = get_playlist_earliest_timestamp(playlist_tracks_df, pl_id)
            else:
                print("⚠️  No 'added_at' column in playlist_tracks.parquet, using playlist order.")
                for i, (name, pl) in enumerate(playlists):
                    earliest_timestamps[pl['playlist_id']] = pd.Timestamp.min if i == 0 else pd.Timestamp.max
        except Exception as e:
            print(f"⚠️  Error reading playlist_tracks.parquet: {e}. Using playlist order.")
            for i, (name, pl) in enumerate(playlists):
                earliest_timestamps[pl['playlist_id']] = pd.Timestamp.min if i == 0 else pd.Timestamp.max
    else:
        print("⚠️  playlist_tracks.parquet not found. Using playlist order to determine older playlist.")
        for i, (name, pl) in enumerate(playlists):
            earliest_timestamps[pl['playlist_id']] = pd.Timestamp.min if i == 0 else pd.Timestamp.max
    
    # Find the oldest playlist
    oldest_name, oldest_pl = min(playlists, key=lambda x: earliest_timestamps.get(x[1]['playlist_id'], pd.Timestamp.max))
    oldest_id = oldest_pl['playlist_id']
    other_playlists = [(name, pl) for name, pl in playlists if name != oldest_name]
    
    print(f"\n🎯 Older playlist (source): {oldest_name} (ID: {oldest_id}, {oldest_pl['track_count']} tracks)")
    print(f"📦 Other playlists ({len(other_playlists)}): {', '.join([name for name, _ in other_playlists])}")
    
    # Get tracks from the oldest playlist
    print(f"\n📥 Fetching tracks from {oldest_name}...")
    oldest_tracks = get_playlist_tracks(sp, oldest_id, force_refresh=True)
    print(f"   Found {len(oldest_tracks)} tracks")
    
    # Rename the oldest playlist
    if oldest_name != new_playlist_name:
        print(f"\n✏️  Renaming '{oldest_name}' to '{new_playlist_name}'...")
        try:
            api_call(sp.user_playlist_change_details, user_id, oldest_id, name=new_playlist_name)
            print(f"   ✓ Renamed: '{oldest_name}' -> '{new_playlist_name}'")
        except Exception as e:
            print(f"   ✗ Failed to rename: {e}")
            raise
    
    # Merge all other playlists
    total_added = 0
    total_duplicates = 0
    deleted_count = 0
    
    for other_name, other_pl in other_playlists:
        other_id = other_pl['playlist_id']
        print(f"\n📥 Fetching tracks from {other_name}...")
        other_tracks = get_playlist_tracks(sp, other_id, force_refresh=True)
        print(f"   Found {len(other_tracks)} tracks")
        
        # Find tracks to add
        tracks_to_add = other_tracks - oldest_tracks
        duplicates = other_tracks & oldest_tracks
        
        print(f"   • Tracks in {new_playlist_name}: {len(oldest_tracks)}")
        print(f"   • Tracks in {other_name}: {len(other_tracks)}")
        print(f"   • Duplicates (will be skipped): {len(duplicates)}")
        print(f"   • Unique tracks to add: {len(tracks_to_add)}")
        
        if tracks_to_add:
            print(f"   ➕ Adding {len(tracks_to_add)} unique tracks from {other_name}...")
            tracks_list = list(tracks_to_add)
            
            chunk_count = 0
            for chunk in chunked(tracks_list, 50):
                chunk_count += 1
                try:
                    api_call(sp.playlist_add_items, oldest_id, chunk)
                except Exception as e:
                    print(f"   ✗ Failed to add chunk {chunk_count}: {e}")
                    raise
            
            oldest_tracks = oldest_tracks | tracks_to_add  # Update track set
            total_added += len(tracks_to_add)
            print(f"   ✓ Successfully added {len(tracks_to_add)} tracks")
        else:
            print(f"   ✅ No new tracks to add from {other_name}")
        
        total_duplicates += len(duplicates)
        
        # Delete other playlist if requested
        if delete_others:
            print(f"   🗑️  Deleting {other_name}...")
            try:
                api_call(sp.user_playlist_unfollow, user_id, other_id)
                print(f"   ✓ Deleted: {other_name}")
                deleted_count += 1
            except Exception as e:
                print(f"   ✗ Failed to delete {other_name}: {e}")
    
    print(f"\n✅ Merge complete!")
    print(f"   • Renamed '{oldest_name}' to '{new_playlist_name}'")
    print(f"   • Added {total_added} unique tracks from {len(other_playlists)} playlist(s)")
    print(f"   • Removed {total_duplicates} duplicates")
    if delete_others:
        print(f"   • Deleted {deleted_count} playlist(s)")

def main():
    parser = argparse.ArgumentParser(description='Merge multiple playlists into one, renaming the oldest to the new name')
    parser.add_argument('playlists', nargs='*', help='New playlist name first, then playlist names to merge (e.g., "New Name" "Playlist1" "Playlist2" ...)')
    parser.add_argument('--new-name', help='Name for the merged playlist (older playlist will be renamed to this)')
    parser.add_argument('--playlists', nargs='+', help='Playlist names to merge')
    parser.add_argument('--keep-others', action='store_true', help='Keep other playlists after merge (default: delete)')
    
    args = parser.parse_args()
    
    # Determine playlists and new name
    if args.new_name and args.playlists:
        new_playlist_name = args.new_name
        playlist_names = args.playlists
    elif len(args.playlists) >= 2:
        new_playlist_name = args.playlists[0]
        playlist_names = args.playlists[1:]
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
    merge_multiple_playlists(sp, playlist_names, new_playlist_name, delete_others=not args.keep_others)

if __name__ == "__main__":
    main()

