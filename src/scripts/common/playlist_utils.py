"""
Playlist utility functions.

Common functions for playlist operations used across multiple scripts.
"""

import pandas as pd
import spotipy
from typing import Optional

from .api_helpers import api_call, chunked


def find_playlist_by_name(playlists_df: pd.DataFrame, name: str) -> pd.Series:
    """
    Find playlist by name (exact match).
    
    Args:
        playlists_df: DataFrame with playlists
        name: Playlist name to find
    
    Returns:
        Series with playlist data
    
    Raises:
        ValueError: If no playlist found or multiple matches
    """
    matches = playlists_df[playlists_df['name'] == name]
    if len(matches) == 0:
        raise ValueError(f"No playlist found with name: {name}")
    if len(matches) > 1:
        raise ValueError(f"Multiple playlists found with name: {name}")
    return matches.iloc[0]


def get_playlist_earliest_timestamp(playlist_tracks_df: pd.DataFrame, playlist_id: str) -> pd.Timestamp:
    """
    Get the earliest added_at timestamp for a playlist.
    
    Args:
        playlist_tracks_df: DataFrame with playlist tracks
        playlist_id: Playlist ID
    
    Returns:
        Earliest timestamp or pd.Timestamp.max if no tracks
    """
    pl_tracks = playlist_tracks_df[playlist_tracks_df['playlist_id'] == playlist_id].copy()
    if len(pl_tracks) == 0:
        return pd.Timestamp.max  # If no tracks, consider it newest
    
    pl_tracks['added_at'] = pd.to_datetime(pl_tracks['added_at'], errors='coerce', utc=True)
    earliest = pl_tracks['added_at'].min()
    if pd.isna(earliest):
        return pd.Timestamp.max  # If no valid timestamps, consider it newest
    return earliest


def get_playlist_tracks(
    sp: spotipy.Spotify,
    playlist_id: str,
    force_refresh: bool = False
) -> set:
    """
    Get all track URIs from a playlist with pagination.
    
    Matches the signature from sync.py for compatibility.
    
    Args:
        sp: Spotify client
        playlist_id: Playlist ID
        force_refresh: Force refresh from API (ignored, kept for compatibility)
    
    Returns:
        Set of track URIs (spotify:track:...)
    """
    uris = set()
    offset = 0
    
    while True:
        try:
            page = api_call(
                sp.playlist_items,
                playlist_id,
                fields="items(track(uri)),next",
                limit=100,
                offset=offset,
            )
            
            for item in page.get("items", []):
                if item.get("track", {}).get("uri"):
                    uris.add(item["track"]["uri"])
            
            if not page.get("next"):
                break
            
            offset += 100
            
        except Exception as e:
            break
    
    return uris


def to_uri(track_id: str) -> str:
    """
    Convert track ID to Spotify URI.
    
    Args:
        track_id: Track ID or URI
    
    Returns:
        Spotify URI
    """
    track_id = str(track_id)
    if track_id.startswith("spotify:track:"):
        return track_id
    if len(track_id) >= 20 and ":" not in track_id:
        return f"spotify:track:{track_id}"
    return track_id


def uri_to_track_id(track_uri: str) -> str:
    """
    Extract track ID from track URI.
    
    Args:
        track_uri: Track URI
    
    Returns:
        Track ID
    """
    if track_uri.startswith("spotify:track:"):
        return track_uri.replace("spotify:track:", "")
    return track_uri


def add_tracks_to_playlist(
    sp: spotipy.Spotify,
    user_id: str,
    playlist_id: str,
    track_uris: list[str],
    verbose: bool = False
) -> None:
    """
    Add tracks to a playlist in chunks.
    
    Args:
        sp: Spotify client
        user_id: User ID
        playlist_id: Playlist ID
        track_uris: List of track URIs to add
        verbose: Enable verbose logging
    """
    if not track_uris:
        return
    
    # Spotify API limit is 100 tracks per request
    for chunk in chunked(track_uris, 100):
        try:
            api_call(
                sp.user_playlist_add_tracks,
                user_id,
                playlist_id,
                chunk,
                verbose=verbose
            )
        except Exception as e:
            if verbose:
                print(f"Error adding tracks: {e}")
            raise

