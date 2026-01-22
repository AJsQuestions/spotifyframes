"""
Common utilities for spotim8 scripts.

Shared functions and setup code used across all scripts.
"""

from .project_path import get_project_root, get_data_dir
from .setup import setup_script_environment
from .api_helpers import get_spotify_client, get_user_info, api_call, chunked
from .playlist_utils import (
    find_playlist_by_name,
    get_playlist_earliest_timestamp,
    get_playlist_tracks,
    to_uri,
    uri_to_track_id,
    add_tracks_to_playlist,
)
from .sync_helpers import trigger_incremental_sync

__all__ = [
    # Path utilities
    "get_project_root",
    "get_data_dir",
    "setup_script_environment",
    # API helpers
    "get_spotify_client",
    "get_user_info",
    "api_call",
    "chunked",
    # Playlist utilities
    "find_playlist_by_name",
    "get_playlist_earliest_timestamp",
    "get_playlist_tracks",
    "to_uri",
    "uri_to_track_id",
    "add_tracks_to_playlist",
    # Sync helpers
    "trigger_incremental_sync",
]

