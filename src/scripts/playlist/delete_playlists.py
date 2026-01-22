#!/usr/bin/env python3
"""
Delete specific playlists from Spotify library.

Usage:
    python scripts/delete_playlists.py "Playlist Name 1" "Playlist Name 2"
    python scripts/delete_playlists.py --ids "playlist_id_1" "playlist_id_2"
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
)

# Setup environment
PROJECT_ROOT = setup_script_environment(__file__)

def delete_playlists_by_name(sp: spotipy.Spotify, playlist_names: list[str]) -> None:
    """Delete playlists by name."""
    # Load playlist data
    data_dir = PROJECT_ROOT / "data"
    playlists_df = pd.read_parquet(data_dir / "playlists.parquet")
    
    # Find matching playlists
    matches = playlists_df[playlists_df['name'].isin(playlist_names)]
    
    if len(matches) == 0:
        print(f"❌ No playlists found matching: {', '.join(playlist_names)}")
        return
    
    print(f"✅ Found {len(matches)} playlist(s) to delete:")
    for _, row in matches.iterrows():
        print(f"   • {row['name']} (ID: {row['playlist_id']})")
    
    # Get user info
    user = get_user_info(sp)
    user_id = user["id"]
    
    # Delete playlists (with backup)
    deleted_count = 0
    for _, row in matches.iterrows():
        playlist_name = row['name']
        playlist_id = row['playlist_id']
        
        try:
            from src.scripts.automation.data_protection import safe_delete_playlist
            success, backup_file = safe_delete_playlist(
                sp, playlist_id, playlist_name,
                create_backup=True
            )
            if success:
                print(f"   ✓ Deleted: {playlist_name}")
                deleted_count += 1
            else:
                print(f"   ⚠️  Deletion failed or aborted: {playlist_name}")
                if backup_file:
                    print(f"   💾 Backup created: {backup_file.name}")
        except Exception as e:
            print(f"   ✗ Failed to delete {playlist_name}: {e}")
    
    print(f"\n✅ Successfully deleted {deleted_count}/{len(matches)} playlist(s)")

def delete_playlists_by_id(sp: spotipy.Spotify, playlist_ids: list[str]) -> None:
    """Delete playlists by ID."""
    # Load playlist data to get names
    data_dir = PROJECT_ROOT / "data"
    playlists_df = pd.read_parquet(data_dir / "playlists.parquet")
    
    # Find matching playlists
    matches = playlists_df[playlists_df['playlist_id'].isin(playlist_ids)]
    
    playlist_names = matches.set_index('playlist_id')['name'].to_dict()
    
    print(f"✅ Found {len(matches)} playlist(s) to delete:")
    for pid in playlist_ids:
        name = playlist_names.get(pid, 'Unknown')
        print(f"   • {name} (ID: {pid})")
    
    # Get user info
    user = get_user_info(sp)
    user_id = user["id"]
    
    # Delete playlists (with backup)
    deleted_count = 0
    for playlist_id in playlist_ids:
        playlist_name = playlist_names.get(playlist_id, 'Unknown')
        
        try:
            from src.scripts.automation.data_protection import safe_delete_playlist
            success, backup_file = safe_delete_playlist(
                sp, playlist_id, playlist_name,
                create_backup=True
            )
            if success:
                print(f"   ✓ Deleted: {playlist_name}")
                deleted_count += 1
            else:
                print(f"   ⚠️  Deletion failed or aborted: {playlist_name}")
                if backup_file:
                    print(f"   💾 Backup created: {backup_file.name}")
        except Exception as e:
            print(f"   ✗ Failed to delete {playlist_name} ({playlist_id}): {e}")
    
    print(f"\n✅ Successfully deleted {deleted_count}/{len(playlist_ids)} playlist(s)")

def main():
    parser = argparse.ArgumentParser(description='Delete playlists from Spotify library')
    parser.add_argument('playlists', nargs='*', help='Playlist names to delete')
    parser.add_argument('--ids', nargs='+', help='Playlist IDs to delete (instead of names)')
    
    args = parser.parse_args()
    
    if not args.playlists and not args.ids:
        parser.print_help()
        exit(1)
    
    # Get authenticated Spotify client
    try:
        sp = get_spotify_client(__file__)
    except Exception as e:
        print(f"❌ Failed to authenticate with Spotify: {e}")
        exit(1)
    
    # Delete playlists
    if args.ids:
        delete_playlists_by_id(sp, args.ids)
    else:
        delete_playlists_by_name(sp, args.playlists)

if __name__ == "__main__":
    main()

