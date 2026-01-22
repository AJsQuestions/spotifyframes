"""
API helper functions for Spotify client operations.

Common functions used across all scripts for authentication and API calls.
"""

import os
import time
import random
import requests
from typing import Callable, TypeVar
from pathlib import Path

import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotipy.exceptions import SpotifyException

from .project_path import get_data_dir

T = TypeVar("T")

# Global adaptive backoff multiplier
_RATE_BACKOFF_MULTIPLIER = 1.0
_RATE_BACKOFF_MAX = 16.0


def get_spotify_client(current_file: str = None) -> spotipy.Spotify:
    """
    Get authenticated Spotify client.
    
    Uses refresh token if available (for CI/CD), otherwise interactive auth.
    
    Args:
        current_file: Path to current file (use __file__) for data directory resolution
    
    Returns:
        Authenticated Spotify client
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
        # Headless auth using refresh token (for CI/CD)
        auth = SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope=scopes
        )
        token_info = auth.refresh_access_token(refresh_token)
        return spotipy.Spotify(auth=token_info["access_token"])
    else:
        # Interactive auth (for local use)
        data_dir = get_data_dir(current_file) if current_file else Path.cwd() / "data"
        auth = SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope=scopes,
            cache_path=str(data_dir / ".cache")
        )
        return spotipy.Spotify(auth_manager=auth)


def get_user_info(sp: spotipy.Spotify) -> dict:
    """
    Get current user information.
    
    Args:
        sp: Spotify client
    
    Returns:
        User information dictionary
    """
    return api_call(sp.current_user)


def api_call(
    fn: Callable[..., T],
    *args,
    max_retries: int = 6,
    backoff_factor: float = 1.0,
    verbose: bool = False,
    **kwargs
) -> T:
    """
    Call Spotify API method with retries and exponential backoff on rate limits.
    
    Args:
        fn: Callable (typically a bound method on a spotipy.Spotify client)
        *args: Positional arguments for fn
        max_retries: Maximum number of retry attempts
        backoff_factor: Base backoff multiplier
        verbose: Enable verbose logging
        **kwargs: Keyword arguments for fn
    
    Returns:
        Result from fn
    
    Raises:
        RuntimeError: If max retries exceeded
    """
    global _RATE_BACKOFF_MULTIPLIER
    
    fn_name = getattr(fn, '__name__', str(fn))
    if verbose:
        print(f"API call: {fn_name}()")
    
    for attempt in range(max_retries):
        try:
            result = fn(*args, **kwargs)
            # Adaptive delay between successful calls
            try:
                base_delay = float(os.environ.get("SPOTIFY_API_DELAY", "0.15"))
            except Exception:
                base_delay = 0.15
            
            delay = base_delay * _RATE_BACKOFF_MULTIPLIER
            if delay and delay > 0:
                time.sleep(delay)
            
            # Decay multiplier on success
            try:
                _RATE_BACKOFF_MULTIPLIER = max(1.0, _RATE_BACKOFF_MULTIPLIER * 0.90)
            except Exception:
                pass
            return result
            
        except Exception as e:
            status = getattr(e, "http_status", None) or getattr(e, "status", None)
            retry_after = None
            headers = getattr(e, "headers", None)
            
            if headers and isinstance(headers, dict):
                retry_after = headers.get("Retry-After") or headers.get("retry-after")
            
            if not retry_after and hasattr(e, "args") and e.args:
                try:
                    for a in e.args:
                        if isinstance(a, dict) and "headers" in a and isinstance(a["headers"], dict):
                            retry_after = a["headers"].get("Retry-After") or a["headers"].get("retry-after")
                            break
                except Exception:
                    pass

            is_rate = status == 429 or (retry_after is not None) or ("rate limit" in str(e).lower())
            is_transient = isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout))

            if is_rate or is_transient:
                wait = backoff_factor * (2 ** attempt) + random.uniform(0, 1)
                if retry_after:
                    try:
                        wait = max(wait, int(retry_after))
                    except Exception:
                        pass
                
                if verbose:
                    print(f"Transient/rate error: {e} — retrying in {wait:.1f}s (attempt {attempt+1}/{max_retries})")
                
                time.sleep(wait)
                
                # Increase adaptive multiplier
                try:
                    _RATE_BACKOFF_MULTIPLIER = min(_RATE_BACKOFF_MAX, _RATE_BACKOFF_MULTIPLIER * 2.0)
                except Exception:
                    pass
                continue

            # Not a retryable error; re-raise
            raise

    # Exhausted retries
    raise RuntimeError(f"API call failed after {max_retries} attempts: {fn}")


def chunked(seq, n=100):
    """
    Yield chunks of sequence.
    
    Args:
        seq: Sequence to chunk
        n: Chunk size
    
    Yields:
        Chunks of the sequence
    """
    for i in range(0, len(seq), n):
        yield seq[i:i+n]

