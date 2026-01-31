"""
Sync catalog: playlists, playlist tracks, user info, genre data.

In-memory caches for the duration of a run; invalidate after modifying playlists.
"""

import pandas as pd
import spotipy

from . import settings
from . import logger
from . import api

# Caches (invalidated by _invalidate_playlist_cache)
_playlist_cache = None
_playlist_cache_valid = False
_playlist_tracks_cache = {}
_user_cache = None
_genre_data_cache = None


def _invalidate_playlist_cache():
    """Invalidate playlist and playlist tracks cache (call after modifying playlists)."""
    global _playlist_cache, _playlist_tracks_cache, _playlist_cache_valid
    _playlist_cache = None
    _playlist_tracks_cache = {}
    _playlist_cache_valid = False


def get_existing_playlists(sp: spotipy.Spotify, force_refresh: bool = False) -> dict:
    """
    Get all user playlists as {name: id}.
    Cached in-memory; call _invalidate_playlist_cache() after creating/deleting playlists.
    """
    global _playlist_cache, _playlist_cache_valid

    if _playlist_cache is not None and not force_refresh and _playlist_cache_valid:
        logger.verbose_log(f"Using cached playlists ({len(_playlist_cache)} playlists)")
        return _playlist_cache

    logger.verbose_log(f"Fetching playlists from API (force_refresh={force_refresh})...")
    mapping = {}
    offset = 0
    while True:
        page = api.api_call(
            sp.current_user_playlists,
            limit=settings.SPOTIFY_API_PAGINATION_LIMIT,
            offset=offset,
        )
        for item in page.get("items", []):
            mapping[item["name"]] = item["id"]
        if not page.get("next"):
            break
        offset += settings.SPOTIFY_API_PAGINATION_LIMIT

    _playlist_cache = mapping
    _playlist_cache_valid = True
    return mapping


def get_playlist_tracks(sp: spotipy.Spotify, playlist_id: str, force_refresh: bool = False) -> set:
    """
    Get all track URIs in a playlist.
    Cached in-memory; invalidated for a playlist when tracks are added.
    """
    global _playlist_tracks_cache

    if playlist_id in _playlist_tracks_cache and not force_refresh:
        logger.verbose_log(
            f"Using cached tracks for playlist {playlist_id} ({len(_playlist_tracks_cache[playlist_id])} tracks)"
        )
        return _playlist_tracks_cache[playlist_id]

    logger.verbose_log(f"Fetching tracks for playlist {playlist_id} from API (force_refresh={force_refresh})...")
    uris = set()
    offset = 0
    while True:
        page = api.api_call(
            sp.playlist_items,
            playlist_id,
            fields="items(track(uri)),next",
            limit=getattr(settings, "SPOTIFY_API_MAX_TRACKS_PER_REQUEST", 100),
            offset=offset,
        )
        for item in page.get("items", []):
            if item.get("track", {}).get("uri"):
                uris.add(item["track"]["uri"])
        if not page.get("next"):
            break
        offset += 100

    _playlist_tracks_cache[playlist_id] = uris
    return uris


def get_user_info(sp: spotipy.Spotify, force_refresh: bool = False) -> dict:
    """Get current user info (cached in-memory)."""
    global _user_cache
    if _user_cache is not None and not force_refresh:
        return _user_cache
    _user_cache = api.api_call(sp.current_user)
    return _user_cache


def _load_genre_data() -> tuple:
    """
    Load genre data from parquet files (artists, track_artists).
    Returns (track_artists, artists) or (None, None) if not available.
    """
    global _genre_data_cache
    if _genre_data_cache is not None:
        return _genre_data_cache
    try:
        track_artists_path = settings.DATA_DIR / "track_artists.parquet"
        artists_path = settings.DATA_DIR / "artists.parquet"
        if not (track_artists_path.exists() and artists_path.exists()):
            _genre_data_cache = (None, None)
            return (None, None)
        track_artists = pd.read_parquet(track_artists_path)
        artists = pd.read_parquet(artists_path)
        _genre_data_cache = (track_artists, artists)
        return (track_artists, artists)
    except Exception as e:
        logger.verbose_log(f"Failed to load genre data: {e}")
        _genre_data_cache = (None, None)
        return (None, None)


