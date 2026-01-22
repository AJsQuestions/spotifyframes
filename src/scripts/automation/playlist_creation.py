"""
Playlist creation utilities.

Functions for creating and updating playlists.
"""

from datetime import datetime
from calendar import monthrange

import spotipy


def create_or_update_playlist(
    sp: spotipy.Spotify,
    user_id: str,
    playlist_name: str,
    track_uris: list,
    description: str,
    existing_playlists: dict,
    period_type: str = "month",
    period_value: str = None
) -> str:
    """
    Create or update a playlist, checking for duplicates and setting period end date.
    
    This function is extracted from sync.py and uses late imports to access
    utilities from sync.py to avoid circular dependencies.
    
    Args:
        sp: Spotify client
        user_id: User ID
        playlist_name: Name of the playlist
        track_uris: List of track URIs to add
        description: Playlist description
        existing_playlists: Dictionary of existing playlists {name: id}
        period_type: "month" or "year" for date calculation
        period_value: "YYYY-MM" for month, "YYYY" for year
    
    Returns:
        Playlist ID
    """
    # Late imports to avoid circular dependencies
    from .sync import (
        log, verbose_log, DATA_DIR, ENABLE_MONTHLY, ENABLE_MOST_PLAYED, ENABLE_DISCOVERY,
        LIKED_SONGS_PLAYLIST_ID, get_playlist_tracks, api_call,
        _chunked, _update_playlist_description_with_genres, _playlist_tracks_cache,
        _invalidate_playlist_cache
    )
    
    # Check for duplicate
    if playlist_name in existing_playlists:
        pid = existing_playlists[playlist_name]
        # Get existing tracks
        already = get_playlist_tracks(sp, pid)
        # Only add tracks that aren't already present
        to_add = [u for u in track_uris if u not in already]
        
        if to_add:
            for chunk in _chunked(to_add, 50):
                api_call(sp.playlist_add_items, pid, chunk)
            # Invalidate cache
            if pid in _playlist_tracks_cache:
                del _playlist_tracks_cache[pid]
            log(f"  {playlist_name}: +{len(to_add)} tracks (total: {len(track_uris)})")
            # Update description with genre tags
            _update_playlist_description_with_genres(sp, user_id, pid, track_uris)
        else:
            log(f"  {playlist_name}: up to date ({len(track_uris)} tracks)")
            # Still update genre tags even if no new tracks
            _update_playlist_description_with_genres(sp, user_id, pid, track_uris)
        return pid
    else:
        # Calculate period end date (for reference, Spotify API doesn't support setting it)
        period_end = None
        if period_value:
            try:
                if period_type == "month":
                    year, month = map(int, period_value.split("-"))
                    last_day = monthrange(year, month)[1]
                    period_end = datetime(year, month, last_day, 23, 59, 59)
                elif period_type == "year":
                    year = int(period_value)
                    period_end = datetime(year, 12, 31, 23, 59, 59)
            except (ValueError, AttributeError):
                pass
        
        # Create new playlist
        pl = api_call(
            sp.user_playlist_create,
            user_id,
            playlist_name,
            public=False,
            description=description,
        )
        pid = pl["id"]
        
        # Add tracks
        for chunk in _chunked(track_uris, 50):
            api_call(sp.playlist_add_items, pid, chunk)
        
        # Update description with genre tags
        _update_playlist_description_with_genres(sp, user_id, pid, track_uris)
        
        # Invalidate cache
        _invalidate_playlist_cache()
        log(f"  {playlist_name}: created with {len(track_uris)} tracks")
        return pid

