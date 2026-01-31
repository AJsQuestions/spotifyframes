#!/usr/bin/env python3
"""
Add unique genre tags to playlist descriptions.

This script:
1. Loads all owned playlists
2. For each playlist, collects all unique genres from artists of tracks in the playlist
3. Updates the playlist description to include genre tags

Usage:
    python scripts/add_genre_tags_to_descriptions.py
    python scripts/add_genre_tags_to_descriptions.py --dry-run  # Preview changes without updating
"""

import argparse
from pathlib import Path
from collections import Counter

import pandas as pd
import spotipy

from src.scripts.common import (
    setup_script_environment,
    get_project_root,
    get_data_dir,
    get_spotify_client,
    get_user_info,
    api_call,
)

# Setup environment
PROJECT_ROOT = setup_script_environment(__file__)
DATA_DIR = get_data_dir(__file__)

def get_playlist_genres(playlist_id: str, playlist_tracks: pd.DataFrame, 
                        track_artists: pd.DataFrame, artists: pd.DataFrame) -> list:
    """Get all unique genres for a playlist from its tracks' artists."""
    # Get all tracks in this playlist
    pl_tracks = playlist_tracks[playlist_tracks['playlist_id'] == playlist_id]
    if len(pl_tracks) == 0:
        return []
    
    # Get all artists for these tracks
    track_ids = pl_tracks['track_id'].unique()
    pl_track_artists = track_artists[track_artists['track_id'].isin(track_ids)]
    
    if len(pl_track_artists) == 0:
        return []
    
    # Get all unique artist IDs
    artist_ids = pl_track_artists['artist_id'].unique()
    
    # Get genres from these artists
    pl_artists = artists[artists['artist_id'].isin(artist_ids)]
    
    # Collect all genres
    all_genres = []
    for idx, genres_list in pl_artists['genres'].items():
        try:
            # Handle different types: list, numpy array, or None
            if genres_list is None:
                continue
            if isinstance(genres_list, (list, tuple)):
                if len(genres_list) > 0:
                    all_genres.extend(genres_list)
            elif hasattr(genres_list, '__iter__') and not isinstance(genres_list, str):
                # Handle numpy arrays and other iterables
                genres_list = list(genres_list)
                if len(genres_list) > 0:
                    all_genres.extend(genres_list)
        except (TypeError, ValueError, AttributeError):
            # Skip if not iterable or has issues
            pass
    
    # Return unique sorted list
    unique_genres = sorted(set(all_genres))
    return unique_genres

def format_genre_tags(genres: list, max_tags: int = 20, max_length: int = 200) -> str:
    """Format genre list as a tag string for playlist description.
    
    Args:
        genres: List of genre strings
        max_tags: Maximum number of genre tags to include
        max_length: Maximum length of the genre tag string (to avoid API limits)
    """
    if not genres:
        return ""
    
    # Limit number of tags to avoid overly long descriptions
    if len(genres) > max_tags:
        genres = genres[:max_tags]
        tag_str = ", ".join(genres) + f" (+{len(genres) - max_tags} more)"
    else:
        tag_str = ", ".join(genres)
    
    # Truncate if still too long (Spotify description limit is ~300 chars, but be safe)
    if len(tag_str) > max_length:
        # Truncate and add ellipsis
        tag_str = tag_str[:max_length - 10] + "..."
    
    return f"Genres: {tag_str}"

def update_playlist_description(sp: spotipy.Spotify, user_id: str, playlist_id: str, 
                               new_description: str, dry_run: bool = False) -> bool:
    """Update playlist description."""
    if dry_run:
        print(f"   [DRY RUN] Would update description to: {new_description[:100]}...")
        return True
    
    try:
        api_call(
            sp.user_playlist_change_details,
            user_id,
            playlist_id,
            description=new_description
        )
        return True
    except Exception as e:
        print(f"   ✗ Failed to update: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Add genre tags to owned playlist descriptions')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Preview changes without updating playlists')
    parser.add_argument('--max-tags', type=int, default=20,
                       help='Maximum number of genre tags to include (default: 20)')
    parser.add_argument('--exclude-liked-songs', action='store_true',
                       help='Exclude Liked Songs playlist from updates')
    
    args = parser.parse_args()
    
    # Load data
    print("📂 Loading data...")
    playlists = pd.read_parquet(DATA_DIR / "playlists.parquet")
    playlist_tracks = pd.read_parquet(DATA_DIR / "playlist_tracks.parquet")
    track_artists = pd.read_parquet(DATA_DIR / "track_artists.parquet")
    artists = pd.read_parquet(DATA_DIR / "artists.parquet")
    
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
        current_description = playlist.get('description', '') or ''
        
        print(f"\n📋 Processing: {playlist_name}")
        
        # Get genres for this playlist
        genres = get_playlist_genres(playlist_id, playlist_tracks, track_artists, artists)
        
        if not genres:
            print(f"   ⚠️  No genres found, skipping")
            skipped_count += 1
            continue
        
        # Format genre tags (limit to 200 chars to avoid API limits)
        genre_tags = format_genre_tags(genres, max_tags=args.max_tags, max_length=200)
        
        if not genre_tags:
            print(f"   ⚠️  No genre tags to add, skipping")
            skipped_count += 1
            continue
        
        # Build new description
        # Spotify API limit is 300 characters for descriptions
        MAX_DESCRIPTION_LENGTH = 300
        
        # If description already has "Genres:" tag, replace it; otherwise append
        if "Genres:" in current_description:
            # Find and replace existing genre tags
            parts = current_description.split("Genres:")
            base_description = parts[0].strip()
            new_description = f"{base_description}\n\n{genre_tags}" if base_description else genre_tags
        else:
            # Append genre tags to existing description
            if current_description:
                new_description = f"{current_description}\n\n{genre_tags}"
            else:
                new_description = genre_tags
        
        # Ensure total description doesn't exceed Spotify's limit
        if len(new_description) > MAX_DESCRIPTION_LENGTH:
            # Truncate the genre tags part if needed
            if current_description:
                # Keep base description, truncate genre tags
                available_space = MAX_DESCRIPTION_LENGTH - len(current_description) - 3  # 3 for "\n\n"
                if available_space > 20:  # Only if we have reasonable space
                    # Recalculate genre tags with smaller max_length
                    genre_tags = format_genre_tags(genres, max_tags=args.max_tags, max_length=available_space - 10)
                    new_description = f"{current_description}\n\n{genre_tags}"
                else:
                    # Not enough space, skip this playlist
                    print(f"   ⚠️  Description would exceed {MAX_DESCRIPTION_LENGTH} chars, skipping")
                    skipped_count += 1
                    continue
            else:
                # No existing description, just truncate genre tags
                genre_tags = format_genre_tags(genres, max_tags=args.max_tags, max_length=MAX_DESCRIPTION_LENGTH - 10)
                new_description = genre_tags
        
        # Only update if description changed
        if new_description == current_description:
            print(f"   ✓ Description already up to date")
            skipped_count += 1
            continue
        
        print(f"   📝 Current: {current_description[:80]}..." if len(current_description) > 80 else f"   📝 Current: {current_description}")
        print(f"   ✨ New: {new_description[:80]}..." if len(new_description) > 80 else f"   ✨ New: {new_description}")
        print(f"   🎵 Found {len(genres)} unique genre(s)")
        
        # Update description
        if update_playlist_description(sp, user_id, playlist_id, new_description, dry_run=args.dry_run):
            updated_count += 1
            if not args.dry_run:
                print(f"   ✅ Updated successfully")
        else:
            error_count += 1
    
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

