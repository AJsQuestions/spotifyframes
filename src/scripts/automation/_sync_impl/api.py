"""
Sync API layer: Spotify client and rate-limited API calls.

Wraps spotipy with retry/backoff and uses standardized api_wrapper.
"""

from typing import Callable, Any
import os
from pathlib import Path

import spotipy
from spotipy.oauth2 import SpotifyOAuth

from src.scripts.common.api_wrapper import api_call as standard_api_call
from src.scripts.common.api_helpers import chunked as chunked_helper

from . import settings
from . import logger


def api_call(
    fn: Callable,
    *args,
    max_retries: int = None,
    backoff_factor: float = 1.0,
    **kwargs
) -> Any:
    """
    Call Spotify API method with retry and error handling.
    """
    if max_retries is None:
        max_retries = settings.API_RATE_LIMIT_MAX_RETRIES
    return standard_api_call(
        fn,
        *args,
        max_retries=max_retries,
        backoff_factor=backoff_factor,
        verbose=logger.get_verbose(),
        **kwargs
    )


def get_spotify_client() -> spotipy.Spotify:
    """
    Get authenticated Spotify client.
    Uses refresh token if available (CI/CD), otherwise interactive auth.
    """
    client_id = os.environ.get("SPOTIPY_CLIENT_ID")
    client_secret = os.environ.get("SPOTIPY_CLIENT_SECRET")
    redirect_uri = os.environ.get("SPOTIPY_REDIRECT_URI", "http://127.0.0.1:8888/callback")
    refresh_token = os.environ.get("SPOTIPY_REFRESH_TOKEN")

    if not all([client_id, client_secret]):
        raise ValueError(
            "Missing SPOTIPY_CLIENT_ID or SPOTIPY_CLIENT_SECRET. "
            "Set them in environment variables or .env file."
        )

    scopes = "user-library-read playlist-modify-private playlist-modify-public playlist-read-private"

    if refresh_token:
        auth = SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope=scopes
        )
        token_info = auth.refresh_access_token(refresh_token)
        return spotipy.Spotify(auth=token_info["access_token"])
    else:
        auth = SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope=scopes,
            cache_path=str(settings.DATA_DIR / ".cache")
        )
        return spotipy.Spotify(auth_manager=auth)


# Backward compatibility: _chunked used by playlist_update, data_protection, etc.
_chunked = chunked_helper
