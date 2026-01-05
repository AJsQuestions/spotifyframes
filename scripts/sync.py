#!/usr/bin/env python3
"""
Unified Spotify Sync & Playlist Update

This script:
1. Syncs your Spotify library to local parquet files using spotim8 (optional)
2. Consolidates old monthly playlists into yearly genre-split playlists
3. Updates monthly playlists with liked songs (last 3 months only)
4. Updates genre-split monthly playlists (HipHop, Dance, Other)
5. Updates master genre playlists

IMPORTANT: This script only ADDS tracks to playlists. It never removes tracks.
Manually added tracks are preserved and will remain in the playlists even after
automated updates. Feel free to manually add tracks to any automatically generated
playlists - they will not be removed.

The script automatically loads environment variables from .env file if python-dotenv
is installed and a .env file exists in the project root.

Usage:
    python scripts/sync.py              # Full sync + update
    python scripts/sync.py --skip-sync  # Update only (fast, uses existing data)
    python scripts/sync.py --sync-only  # Sync only, no playlist changes
    python scripts/sync.py --all-months # Process all months, not just current

Environment Variables (set in .env file or environment):
    Required:
        SPOTIPY_CLIENT_ID       - Spotify app client ID
        SPOTIPY_CLIENT_SECRET   - Spotify app client secret
    
    Optional:
        SPOTIPY_REDIRECT_URI    - Redirect URI (default: http://127.0.0.1:8888/callback)
        SPOTIPY_REFRESH_TOKEN   - Refresh token for headless/CI auth
        PLAYLIST_OWNER_NAME     - Prefix for playlist names (default: "AJ")
        PLAYLIST_PREFIX         - Month playlist prefix (default: "Finds")
        
        Email Notifications (optional):
        EMAIL_ENABLED           - Enable email notifications (true/false)
        EMAIL_SMTP_HOST         - SMTP server (e.g., smtp.gmail.com)
        EMAIL_SMTP_PORT         - SMTP port (default: 587)
        EMAIL_SMTP_USER         - SMTP username
        EMAIL_SMTP_PASSWORD     - SMTP password (use app password for Gmail)
        EMAIL_TO                - Recipient email address
        EMAIL_FROM              - Sender email (defaults to EMAIL_SMTP_USER)
        EMAIL_SUBJECT_PREFIX    - Subject prefix (default: "[Spotify Sync]")

Run locally or via cron:
    # Direct run (loads .env automatically):
    python scripts/sync.py
    
    # Via wrapper (for cron):
    python scripts/runner.py
    
    # Linux/Mac cron (every day at 2am):
    0 2 * * * cd /path/to/spotim8 && /path/to/venv/bin/python scripts/runner.py
"""

import argparse
import ast
import io
import os
import random
import sys
import time
import warnings
from collections import Counter
from datetime import datetime
from pathlib import Path
from dateutil.relativedelta import relativedelta
from contextlib import contextmanager

# Suppress urllib3/OpenSSL warnings (common on macOS with LibreSSL)
warnings.filterwarnings("ignore", message=".*urllib3.*OpenSSL.*", category=UserWarning)
warnings.filterwarnings("ignore", category=UserWarning, module="urllib3")

import numpy as np
import pandas as pd
import requests
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from tqdm import tqdm

# Suppress pandas Period timezone warnings
warnings.filterwarnings('ignore', category=UserWarning, message='.*Converting to PeriodArray.*')

# Try to load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False

# Adaptive backoff multiplier (increases after rate errors, decays on success)
_RATE_BACKOFF_MULTIPLIER = 1.0
_RATE_BACKOFF_MAX = 16.0

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import spotim8 for full library sync (required)
from spotim8 import Spotim8, CacheConfig, set_response_cache, sync_all_export_data

# Import genre classification functions from shared module
from spotim8.genres import (
    SPLIT_GENRES,
    get_split_genre, get_broad_genre,
    get_all_split_genres, get_all_broad_genres
)

# Import comprehensive genre inference
from spotim8.genre_inference import (
    infer_genres_comprehensive,
    enhance_artist_genres_from_playlists
)

# Import email notification module
try:
    import importlib.util
    email_notify_path = Path(__file__).parent / "email_notify.py"
    if email_notify_path.exists():
        spec = importlib.util.spec_from_file_location("email_notify", email_notify_path)
        email_notify = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(email_notify)
        send_email_notification = email_notify.send_email_notification
        is_email_enabled = email_notify.is_email_enabled
        EMAIL_AVAILABLE = True
    else:
        EMAIL_AVAILABLE = False
except Exception:
    EMAIL_AVAILABLE = False


# ============================================================================
# CONFIGURATION - Set via environment variables
# ============================================================================

OWNER_NAME = os.environ.get("PLAYLIST_OWNER_NAME", "AJ")

# Individual prefixes for different playlist types
# If not set, falls back to PLAYLIST_PREFIX, then "Finds"
BASE_PREFIX = os.environ.get("PLAYLIST_PREFIX", "Finds")

# Playlist type enable/disable flags (from .env)
def _parse_bool_env(key: str, default: bool = True) -> bool:
    """Parse boolean environment variable."""
    value = os.environ.get(key, str(default)).lower()
    return value in ("true", "1", "yes", "on")

ENABLE_MONTHLY = _parse_bool_env("PLAYLIST_ENABLE_MONTHLY", True)
ENABLE_MOST_PLAYED = _parse_bool_env("PLAYLIST_ENABLE_MOST_PLAYED", True)
# ENABLE_TIME_BASED removed - Vibes playlists no longer supported
# ENABLE_TIME_BASED = _parse_bool_env("PLAYLIST_ENABLE_TIME_BASED", True)
# ENABLE_REPEAT removed - OnRepeat playlists no longer supported
# ENABLE_REPEAT = _parse_bool_env("PLAYLIST_ENABLE_REPEAT", True)
ENABLE_DISCOVERY = _parse_bool_env("PLAYLIST_ENABLE_DISCOVERY", True)

PREFIX_MONTHLY = os.environ.get("PLAYLIST_PREFIX_MONTHLY", BASE_PREFIX)
PREFIX_GENRE_MONTHLY = os.environ.get("PLAYLIST_PREFIX_GENRE_MONTHLY", BASE_PREFIX)
PREFIX_YEARLY = os.environ.get("PLAYLIST_PREFIX_YEARLY", BASE_PREFIX)
PREFIX_GENRE_MASTER = os.environ.get("PLAYLIST_PREFIX_GENRE_MASTER", "am")
PREFIX_MOST_PLAYED = os.environ.get("PLAYLIST_PREFIX_MOST_PLAYED", "Top")
PREFIX_TIME_BASED = os.environ.get("PLAYLIST_PREFIX_TIME_BASED", "Vibes")
PREFIX_REPEAT = os.environ.get("PLAYLIST_PREFIX_REPEAT", "OnRepeat")
PREFIX_DISCOVERY = os.environ.get("PLAYLIST_PREFIX_DISCOVERY", "Discovery")

# Playlist naming templates (can be customized via env vars)
MONTHLY_NAME_TEMPLATE = os.environ.get(
    "PLAYLIST_TEMPLATE_MONTHLY",
    "{owner}{prefix}{mon}{year}"
)
YEARLY_NAME_TEMPLATE = os.environ.get(
    "PLAYLIST_TEMPLATE_YEARLY",
    "{owner}{prefix}{year}"
)
GENRE_MONTHLY_TEMPLATE = os.environ.get(
    "PLAYLIST_TEMPLATE_GENRE_MONTHLY",
    "{genre}{prefix}{mon}{year}"
)
GENRE_YEARLY_TEMPLATE = os.environ.get(
    "PLAYLIST_TEMPLATE_GENRE_YEARLY",
    "{genre}{prefix}{year}"
)
GENRE_NAME_TEMPLATE = os.environ.get(
    "PLAYLIST_TEMPLATE_GENRE_MASTER",
    "{owner}{prefix}{genre}"
)
MOST_PLAYED_TEMPLATE = os.environ.get(
    "PLAYLIST_TEMPLATE_MOST_PLAYED",
    "{owner}{prefix}{mon}{year}"
)
TIME_BASED_TEMPLATE = os.environ.get(
    "PLAYLIST_TEMPLATE_TIME_BASED",
    "{owner}{prefix}{mon}{year}"  # Monthly format, can also use {type} for time-specific
)
REPEAT_TEMPLATE = os.environ.get(
    "PLAYLIST_TEMPLATE_REPEAT",
    "{owner}{prefix}{mon}{year}"  # Monthly format
)
DISCOVERY_TEMPLATE = os.environ.get(
    "PLAYLIST_TEMPLATE_DISCOVERY",
    "{owner}{prefix}{mon}{year}"
)

# Master genre playlist limits
MIN_TRACKS_FOR_GENRE = 20
MAX_GENRE_PLAYLISTS = 19

# Monthly playlist retention (how many recent months to keep as monthly playlists)
KEEP_MONTHLY_MONTHS = int(os.environ.get("KEEP_MONTHLY_MONTHS", "3"))

# Playlist formatting options
DATE_FORMAT = os.environ.get("PLAYLIST_DATE_FORMAT", "short")  # short, medium, long, numeric
SEPARATOR_MONTH = os.environ.get("PLAYLIST_SEPARATOR_MONTH", "none")  # none, space, dash, underscore
SEPARATOR_PREFIX = os.environ.get("PLAYLIST_SEPARATOR_PREFIX", "none")  # none, space, dash, underscore
CAPITALIZATION = os.environ.get("PLAYLIST_CAPITALIZATION", "preserve")  # title, upper, lower, preserve
DESCRIPTION_TEMPLATE = os.environ.get(
    "PLAYLIST_DESCRIPTION_TEMPLATE",
    "{description} from {period} (automatically updated; manual additions welcome)"
)

# Paths
DATA_DIR = PROJECT_ROOT / "data"
LIKED_SONGS_PLAYLIST_ID = "__liked_songs__"  # Match spotim8 library constant

# Month name mapping (short, medium, long)
MONTH_NAMES_SHORT = {
    "01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr",
    "05": "May", "06": "Jun", "07": "Jul", "08": "Aug",
    "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dec"
}
MONTH_NAMES_MEDIUM = {
    "01": "January", "02": "February", "03": "March", "04": "April",
    "05": "May", "06": "June", "07": "July", "08": "August",
    "09": "September", "10": "October", "11": "November", "12": "December"
}
MONTH_NAMES = MONTH_NAMES_SHORT  # Default to short for backward compatibility

# Genre classification functions:
# - get_split_genre() - Maps tracks to HipHop, Dance, or Other
# - get_broad_genre() - Maps tracks to broad categories (Hip-Hop, Electronic, etc.)
# - SPLIT_GENRES - List of split genres: ["HipHop", "Dance", "Other"]


# ============================================================================
# UTILITIES
# ============================================================================

# Global log buffer for email notifications
_log_buffer = []

def log(msg: str) -> None:
    """Print message with timestamp and optionally buffer for email.
    
    Uses tqdm.write() to avoid interfering with progress bars.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {msg}"
    # Use tqdm.write() to avoid interfering with progress bars
    try:
        tqdm.write(log_line)
    except NameError:
        # tqdm not imported yet, use regular print
        print(log_line)
    
    # Buffer log for email notification
    if EMAIL_AVAILABLE and is_email_enabled():
        _log_buffer.append(log_line)

# Set log function for genre_inference module (after log is defined)
import spotim8.genre_inference as genre_inference_module
genre_inference_module._log_fn = log


@contextmanager
def timed_step(step_name: str):
    """Context manager to time and log execution of a step."""
    start_time = time.time()
    log(f"⏱️  [START] {step_name}")
    try:
        yield
    finally:
        elapsed = time.time() - start_time
        log(f"⏱️  [END] {step_name} (took {elapsed:.2f}s)")


def api_call(fn, *args, max_retries: int = 6, backoff_factor: float = 1.0, **kwargs):
    """Call Spotify API method `fn` with retries and exponential backoff on rate limits or transient errors.

    `fn` should be a callable (typically a bound method on a `spotipy.Spotify` client).
    The helper inspects exception attributes for 429/retry-after and uses exponential backoff.
    """
    global _RATE_BACKOFF_MULTIPLIER

    for attempt in range(max_retries):
        try:
            result = fn(*args, **kwargs)
            # Adaptive short delay between successful calls to avoid bursting the API
            try:
                base_delay = float(os.environ.get("SPOTIFY_API_DELAY", "0.15"))
            except Exception:
                base_delay = 0.15
            # Multiply by adaptive multiplier (increases when we hit rate limits)
            delay = base_delay * _RATE_BACKOFF_MULTIPLIER
            if delay and delay > 0:
                time.sleep(delay)
            # Decay multiplier slowly towards 1.0 on success
            try:
                _RATE_BACKOFF_MULTIPLIER = max(1.0, _RATE_BACKOFF_MULTIPLIER * 0.90)
            except Exception:
                pass
            return result
        except Exception as e:
            status = getattr(e, "http_status", None) or getattr(e, "status", None)
            # Try to find a Retry-After header if present
            retry_after = None
            headers = getattr(e, "headers", None)
            if headers and isinstance(headers, dict):
                retry_after = headers.get("Retry-After") or headers.get("retry-after")
            # Spotipy may include the underlying response in args; try common locations
            if not retry_after and hasattr(e, "args") and e.args:
                try:
                    # args may include a dict with 'headers'
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
                log(f"Transient/rate error: {e} — retrying in {wait:.1f}s (attempt {attempt+1}/{max_retries})")
                time.sleep(wait)
                # Increase adaptive multiplier to throttle further successful calls
                try:
                    _RATE_BACKOFF_MULTIPLIER = min(_RATE_BACKOFF_MAX, _RATE_BACKOFF_MULTIPLIER * 2.0)
                except Exception:
                    pass
                continue

            # Not a retryable error; re-raise
            raise

    # Exhausted retries
    raise RuntimeError(f"API call failed after {max_retries} attempts: {fn}")


def get_spotify_client() -> spotipy.Spotify:
    """
    Get authenticated Spotify client.
    
    Uses refresh token if available (for CI/CD), otherwise interactive auth.
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
        auth = SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope=scopes,
            cache_path=str(DATA_DIR / ".cache")
        )
        return spotipy.Spotify(auth_manager=auth)


def _chunked(seq, n=100):
    """Yield chunks of sequence."""
    for i in range(0, len(seq), n):
        yield seq[i:i+n]


def _to_uri(track_id: str) -> str:
    """Convert track ID to Spotify URI."""
    track_id = str(track_id)
    if track_id.startswith("spotify:track:"):
        return track_id
    if len(track_id) >= 20 and ":" not in track_id:
        return f"spotify:track:{track_id}"
    return track_id


def _parse_genres(genre_data) -> list:
    """Parse genre data from various formats."""
    # Handle None or empty
    if genre_data is None:
        return []
    # Handle numpy arrays first (before checking truthiness which fails on arrays)
    if isinstance(genre_data, np.ndarray):
        return list(genre_data) if len(genre_data) > 0 else []
    # Handle empty collections
    if not genre_data:
        return []
    if isinstance(genre_data, list):
        return genre_data
    if isinstance(genre_data, str):
        try:
            return ast.literal_eval(genre_data)
        except (ValueError, SyntaxError):
            return [genre_data]
    return []


def _get_all_track_genres(track_id: str, track_artists: pd.DataFrame, artist_genres_map: dict) -> list:
    """Get all genres from all artists on a track.
    
    Collects genres from ALL artists on the track (not just the primary artist)
    to get more complete genre information for better classification.
    
    Args:
        track_id: The track ID
        track_artists: DataFrame with track_id and artist_id columns
        artist_genres_map: Dictionary mapping artist_id to genres list
    
    Returns:
        Combined list of all unique genres from all artists on the track
    """
    # Get all artists for this track
    track_artist_rows = track_artists[track_artists["track_id"] == track_id]
    
    # Collect all genres from all artists
    all_genres = []
    for _, row in track_artist_rows.iterrows():
        artist_id = row["artist_id"]
        artist_genres = _parse_genres(artist_genres_map.get(artist_id, []))
        all_genres.extend(artist_genres)
    
    # Return unique genres while preserving order
    seen = set()
    unique_genres = []
    for genre in all_genres:
        if genre not in seen:
            seen.add(genre)
            unique_genres.append(genre)
    
    return unique_genres


# ============================================================================
# FORMATTING HELPERS
# ============================================================================

def _get_separator(sep_type: str) -> str:
    """Get separator character based on type."""
    sep_map = {
        "none": "",
        "space": " ",
        "dash": "-",
        "underscore": "_",
    }
    return sep_map.get(sep_type.lower(), "")


def _format_date(month_str: str = None, year: str = None) -> tuple:
    """
    Format date components based on DATE_FORMAT setting.
    
    Returns:
        (month_str, year_str) tuple with formatted components
    """
    mon = ""
    year_str = ""
    
    if month_str:
        parts = month_str.split("-")
        full_year = parts[0] if len(parts) >= 1 else ""
        month_num = parts[1] if len(parts) >= 2 else ""
        
        if DATE_FORMAT == "numeric":
            mon = month_num
            year_str = full_year
        elif DATE_FORMAT == "medium":
            mon = MONTH_NAMES_MEDIUM.get(month_num, month_num)
            year_str = full_year
        elif DATE_FORMAT == "long":
            mon = MONTH_NAMES_MEDIUM.get(month_num, month_num)
            year_str = full_year
        else:  # short (default)
            mon = MONTH_NAMES_SHORT.get(month_num, month_num)
            year_str = full_year[2:] if len(full_year) == 4 else full_year
    elif year:
        # Handle year parameter if provided directly
        if DATE_FORMAT == "numeric":
            year_str = year
        else:
            year_str = year[2:] if len(year) == 4 else year
    
    # Apply separator between month and year if both present
    if mon and year_str and SEPARATOR_MONTH != "none":
        sep = _get_separator(SEPARATOR_MONTH)
        if DATE_FORMAT == "medium" or DATE_FORMAT == "long":
            # For medium/long, add space before year: "November 2024"
            mon = f"{mon}{sep}{year_str}"
            year_str = ""  # Year is now part of mon
        else:
            # For short/numeric, keep them separate for template
            pass
    
    return mon, year_str


def _apply_capitalization(text: str) -> str:
    """Apply capitalization style to text."""
    if CAPITALIZATION == "upper":
        return text.upper()
    elif CAPITALIZATION == "lower":
        return text.lower()
    elif CAPITALIZATION == "title":
        return text.title()
    else:  # preserve
        return text


def format_playlist_name(template: str, month_str: str = None, genre: str = None, 
                         prefix: str = None, playlist_type: str = "monthly", year: str = None) -> str:
    """Format playlist name from template.
    
    Args:
        template: Template string with placeholders
        month_str: Month string like '2025-01' (optional)
        genre: Genre name (optional)
        prefix: Override prefix (optional, uses type-specific prefix if not provided)
        playlist_type: Type of playlist to determine prefix ("monthly", "genre_monthly", 
                      "yearly", "genre_master", "most_played", "time_based", "repeat", "discovery")
    """
    # Determine prefix based on playlist type if not provided
    if prefix is None:
        prefix_map = {
            "monthly": PREFIX_MONTHLY,
            "genre_monthly": PREFIX_GENRE_MONTHLY,
            "yearly": PREFIX_YEARLY,
            "genre_master": PREFIX_GENRE_MASTER,
            "most_played": PREFIX_MOST_PLAYED,
            # "time_based": PREFIX_TIME_BASED,  # Vibes removed
            # "repeat": PREFIX_REPEAT,  # OnRepeat removed
            "discovery": PREFIX_DISCOVERY,
        }
        prefix = prefix_map.get(playlist_type, BASE_PREFIX)
    
    # Format date components
    mon, year_str = _format_date(month_str, year)
    
    # Check if month already includes year (for medium/long formats)
    month_includes_year = (DATE_FORMAT == "medium" or DATE_FORMAT == "long") and mon and not year_str
    
    # Build components (before capitalization)
    owner = OWNER_NAME
    prefix_str = prefix
    genre_str = genre or ""
    
    # Apply capitalization
    owner = _apply_capitalization(owner)
    prefix_str = _apply_capitalization(prefix_str)
    genre_str = _apply_capitalization(genre_str)
    mon = _apply_capitalization(mon)
    year_str = _apply_capitalization(year_str)
    
    # Apply separators before formatting
    prefix_sep = _get_separator(SEPARATOR_PREFIX)
    month_sep = _get_separator(SEPARATOR_MONTH) if mon and year_str and not month_includes_year else ""
    
    # Build formatted components with separators
    if SEPARATOR_PREFIX != "none" and prefix_str:
        # Add separator between owner and prefix if both present
        owner_prefix = f"{owner}{prefix_sep}{prefix_str}" if owner else prefix_str
    else:
        owner_prefix = f"{owner}{prefix_str}" if owner else prefix_str
    
    # Handle month/year separator
    date_includes_year = False
    if month_includes_year:
        # Month already includes year (e.g., "November 2024")
        date_part = mon
        date_includes_year = True
    elif mon and year_str:
        # Add separator between month and year
        date_part = f"{mon}{month_sep}{year_str}" if month_sep else f"{mon}{year_str}"
        date_includes_year = True  # date_part now includes the year
    elif mon:
        date_part = mon
    elif year_str:
        # Only year, no month - keep them separate for template replacement
        date_part = ""
        date_includes_year = False  # Year should be replaced separately in template
    else:
        date_part = ""
    
    # Format the name using components
    # Replace template placeholders with formatted components
    formatted = template
    formatted = formatted.replace("{owner}", owner)
    formatted = formatted.replace("{prefix}", prefix_str)
    formatted = formatted.replace("{genre}", genre_str)
    formatted = formatted.replace("{mon}", date_part if (mon or month_includes_year) else "")
    # Only replace {year} if date_part doesn't already include it
    formatted = formatted.replace("{year}", "" if date_includes_year else (year_str if year_str else ""))
    
    # If template uses {owner}{prefix} pattern, replace with combined version
    if "{owner}{prefix}" in template or (owner and prefix_str and owner_prefix != f"{owner}{prefix_str}"):
        # Try to replace owner+prefix combination
        formatted = formatted.replace(f"{owner}{prefix_str}", owner_prefix)
    
    return formatted


def format_playlist_description(description: str, period: str = None, date: str = None, 
                                playlist_type: str = None, genre: str = None) -> str:
    """
    Format playlist description using template.
    
    Args:
        description: Base description text
        period: Period string (e.g., "Nov 2024", "2024")
        date: Specific date string
        playlist_type: Type of playlist
        genre: Genre name
    
    Returns:
        Formatted description string
    """
    return DESCRIPTION_TEMPLATE.format(
        description=description or "",
        period=period or "",
        date=date or "",
        type=playlist_type or "",
        genre=genre or ""
    )


def format_yearly_playlist_name(year: str) -> str:
    """Format yearly playlist name like 'AJFinds2025'."""
    # Handle both 4-digit and 2-digit years
    if len(year) == 4:
        year_short = year[2:]
    else:
        year_short = year
    
    return format_playlist_name(YEARLY_NAME_TEMPLATE, year=year_short, playlist_type="yearly")


# ============================================================================
# SPOTIFY API HELPERS (with smart caching)
# ============================================================================

# In-memory caches (per-run, invalidated when needed)
_playlist_cache: dict = None  # {name: id}
_playlist_tracks_cache: dict = {}  # {playlist_id: set of URIs}
_user_cache: dict = None  # user info
_playlist_cache_valid = False

def _invalidate_playlist_cache():
    """Invalidate playlist and playlist tracks cache (call after modifying playlists)."""
    global _playlist_cache, _playlist_tracks_cache, _playlist_cache_valid
    _playlist_cache = None
    _playlist_tracks_cache = {}
    _playlist_cache_valid = False

def get_existing_playlists(sp: spotipy.Spotify, force_refresh: bool = False) -> dict:
    """Get all user playlists as {name: id} mapping.
    
    Cached in-memory for the duration of the run. Call _invalidate_playlist_cache()
    after modifying playlists (creating/deleting) to ensure fresh data.
    """
    global _playlist_cache, _playlist_cache_valid
    
    if _playlist_cache is not None and not force_refresh and _playlist_cache_valid:
        return _playlist_cache
    
    mapping = {}
    offset = 0
    while True:
        page = api_call(sp.current_user_playlists, limit=50, offset=offset)
        for item in page.get("items", []):
            mapping[item["name"]] = item["id"]
        if not page.get("next"):
            break
        offset += 50
    
    _playlist_cache = mapping
    _playlist_cache_valid = True
    return mapping


def get_playlist_tracks(sp: spotipy.Spotify, playlist_id: str, force_refresh: bool = False) -> set:
    """Get all track URIs in a playlist.
    
    Cached in-memory for the duration of the run. Cache is automatically
    invalidated for a playlist when tracks are added to it.
    """
    global _playlist_tracks_cache
    
    if playlist_id in _playlist_tracks_cache and not force_refresh:
        return _playlist_tracks_cache[playlist_id]
    
    uris = set()
    offset = 0
    while True:
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
    
    _playlist_tracks_cache[playlist_id] = uris
    return uris


def get_user_info(sp: spotipy.Spotify, force_refresh: bool = False) -> dict:
    """Get current user info (cached in-memory)."""
    global _user_cache
    
    if _user_cache is not None and not force_refresh:
        return _user_cache
    
    _user_cache = api_call(sp.current_user)
    return _user_cache


# ============================================================================
# DATA SYNC FUNCTIONS
# ============================================================================

def compute_track_genres_incremental(stats: dict = None) -> None:
    """Compute and store track genres with smart caching.
    
    Only re-infers genres for tracks that have changed:
    - New tracks (not yet inferred)
    - Tracks in playlists that were updated
    - Tracks whose artists had genres enhanced
    
    This dramatically improves sync runtime by avoiding unnecessary computation.
    """
    log("\n--- Computing Track Genres (Smart Caching) ---")
    
    try:
        # Load all data
        tracks_path = DATA_DIR / "tracks.parquet"
        track_artists_path = DATA_DIR / "track_artists.parquet"
        artists_path = DATA_DIR / "artists.parquet"
        playlist_tracks_path = DATA_DIR / "playlist_tracks.parquet"
        playlists_path = DATA_DIR / "playlists.parquet"
        
        if not all(p.exists() for p in [tracks_path, track_artists_path, artists_path, playlist_tracks_path, playlists_path]):
            log("  ⚠️  Missing required data files, skipping genre computation")
            return
        
        # Check file modification times for smart caching
        playlist_tracks_mtime = playlist_tracks_path.stat().st_mtime if playlist_tracks_path.exists() else 0
        playlists_mtime = playlists_path.stat().st_mtime if playlists_path.exists() else 0
        
        tracks = pd.read_parquet(tracks_path)
        track_artists = pd.read_parquet(track_artists_path)
        artists = pd.read_parquet(artists_path)
        playlist_tracks = pd.read_parquet(playlist_tracks_path)
        playlists = pd.read_parquet(playlists_path)
        
        # Check if genres column exists, if not create it
        if "genres" not in tracks.columns:
            tracks["genres"] = None
        
        # Determine which tracks need genre inference
        tracks_needing_inference = set()
        
        # 1. Tracks without genres
        def needs_genres(genres_val):
            """Check if track needs genre inference."""
            # Handle None
            if genres_val is None:
                return True
            
            # Handle numpy arrays first (before checking isna which fails on arrays)
            if isinstance(genres_val, np.ndarray):
                return len(genres_val) == 0
            
            # Check if it's a list
            if isinstance(genres_val, list):
                return len(genres_val) == 0
            
            # Check if NaN (but only for scalar values, use try-except to handle arrays)
            try:
                # First check if it's a scalar by trying to use pd.isna
                scalar_check = pd.api.types.is_scalar(genres_val)
                if scalar_check:
                    if pd.isna(genres_val):
                        return True
            except (ValueError, TypeError):
                # If isna fails (e.g., on arrays), continue to next check
                pass
            
            # For other types (including arrays), try to check length
            try:
                if hasattr(genres_val, '__len__'):
                    return len(genres_val) == 0
            except (TypeError, AttributeError):
                pass
            
            # Unknown type or couldn't determine - treat as needing genres
            return True
        
        tracks_without_genres = tracks[tracks["genres"].apply(needs_genres)]
        tracks_needing_inference.update(tracks_without_genres["track_id"].tolist())
        
        # 2. New tracks added in this sync (if stats provided)
        if stats and stats.get("tracks_added", 0) > 0:
            # Find tracks in playlist_tracks that don't have genres yet
            playlist_track_ids = set(playlist_tracks["track_id"].unique())
            # Helper function to check if track has valid genres
            def has_valid_genres(genres_val):
                if genres_val is None or pd.isna(genres_val):
                    return False
                if isinstance(genres_val, list):
                    return len(genres_val) > 0
                return False
            
            tracks_with_genres = set(tracks[tracks["genres"].apply(has_valid_genres)]["track_id"].tolist())
            new_track_ids = playlist_track_ids - tracks_with_genres
            tracks_needing_inference.update(new_track_ids)
        
        total_tracks = len(tracks)
        needs_inference = len(tracks_needing_inference)
        already_has_genres = total_tracks - needs_inference
        
        if needs_inference == 0:
            log(f"  ✅ All {total_tracks:,} tracks already have genres (smart cache hit)")
            return
        
        log(f"  📊 Genre status: {already_has_genres:,} cached, {needs_inference:,} need inference")
        
        # Only enhance artist genres if playlists changed (smart caching)
        # Skip if most tracks already have genres (enhancement is expensive and not needed)
        if stats and (stats.get("playlists_updated", 0) > 0 or stats.get("tracks_added", 0) > 0):
            # Quick check: if we already have most tracks with genres, skip enhancement
            # (it's expensive - iterates through all artists and playlists)
            tracks_with_genres_pct = (already_has_genres / total_tracks * 100) if total_tracks > 0 else 0
            if tracks_with_genres_pct < 90:
                # Less than 90% have genres - enhancement might help
                # But limit to reasonable number of artists to avoid timeout
                artists_without_genres = artists[artists["genres"].apply(
                    lambda g: g is None or (isinstance(g, list) and len(g) == 0) or 
                    (pd.api.types.is_scalar(g) and pd.isna(g))
                )]
                
                if len(artists_without_genres) > 500:
                    log(f"  ⏭️  Skipping artist genre enhancement (too many artists without genres: {len(artists_without_genres):,})")
                else:
                    tqdm.write("  🔄 Enhancing artist genres from playlist patterns...")
                    artists_before = artists.copy()
                    artists_enhanced = enhance_artist_genres_from_playlists(
                        artists, track_artists, playlist_tracks, playlists
                    )
                    
                    # Check if any artists had their genres enhanced
                    enhanced_artist_ids = set()
                    artists_dict_before = artists_before.set_index("artist_id")["genres"].to_dict()
                    artists_dict_after = artists_enhanced.set_index("artist_id")["genres"].to_dict()
                    
                    for artist_id in artists_dict_after.keys():
                        old_genres = set(_parse_genres(artists_dict_before.get(artist_id, [])))
                        new_genres = set(_parse_genres(artists_dict_after.get(artist_id, [])))
                        if old_genres != new_genres:
                            enhanced_artist_ids.add(artist_id)
                    
                    if enhanced_artist_ids:
                        # Save enhanced artists back
                        artists_enhanced.to_parquet(artists_path, index=False)
                        artists = artists_enhanced
                        # Re-infer genres for tracks by enhanced artists
                        enhanced_track_ids = track_artists[track_artists["artist_id"].isin(enhanced_artist_ids)]["track_id"].unique()
                        tracks_needing_inference.update(enhanced_track_ids)
                        tqdm.write(f"  ✨ Enhanced {len(enhanced_artist_ids)} artists - re-inferring {len(enhanced_track_ids)} tracks")
                    else:
                        artists = artists_enhanced  # Use enhanced even if no changes (for consistency)
            else:
                log(f"  ⏭️  Skipping artist genre enhancement ({tracks_with_genres_pct:.1f}% tracks already have genres)")
        else:
            log("  ⏭️  Skipping artist genre enhancement (no playlist changes)")
        
        # Filter to only tracks that need inference
        tracks_to_process = tracks[tracks["track_id"].isin(tracks_needing_inference)]
        
        if len(tracks_to_process) == 0:
            log(f"  ✅ All tracks up to date (smart cache hit)")
            return
        
        tqdm.write(f"  🔄 Inferring genres for {len(tracks_to_process):,} track(s)...")
        
        # Infer genres for tracks that need it
        inferred_genres_map = {}
        
        # Use tqdm for progress bar
        track_iterator = tracks_to_process.itertuples()
        if len(tracks_to_process) > 0:
            track_iterator = tqdm(
                track_iterator,
                total=len(tracks_to_process),
                desc="  Inferring genres",
                unit="track",
                ncols=100,
                leave=False
            )
        
        for track_row in track_iterator:
            track_id = track_row.track_id
            track_name = getattr(track_row, 'name', None)
            album_name = getattr(track_row, 'album_name', None)
            
            genres = infer_genres_comprehensive(
                track_id=track_id,
                track_name=track_name,
                album_name=album_name,
                track_artists=track_artists,
                artists=artists,
                playlist_tracks=playlist_tracks,
                playlists=playlists,
                mode="split"  # Use split genres for tracks
            )
            
            inferred_genres_map[track_id] = genres
        
        # Update tracks with inferred genres
        if inferred_genres_map:
            tqdm.write("  💾 Updating track genres...")
            for track_id, genres in inferred_genres_map.items():
                track_mask = tracks["track_id"] == track_id
                track_rows = tracks[track_mask]
                if len(track_rows) > 0:
                    # Use .at for scalar assignment of list values
                    track_idx_val = track_rows.index[0]
                    tracks.at[track_idx_val, "genres"] = genres
            
            # Save updated tracks
            tracks.to_parquet(tracks_path, index=False)
        
        # Count tracks with valid genres (avoiding pandas array ambiguity)
        def has_valid_genre(g):
            if g is None:
                return False
            try:
                if pd.api.types.is_scalar(g):
                    if pd.isna(g):
                        return False
                if isinstance(g, list):
                    return len(g) > 0
                if isinstance(g, (np.ndarray, pd.Series)):
                    return len(g) > 0
                return bool(g)
            except (ValueError, TypeError):
                return False
        
        tracks_with_genres_after = tracks["genres"].apply(has_valid_genre).sum()
        log(f"  ✅ Inferred genres for {len(inferred_genres_map):,} track(s) ({tracks_with_genres_after:,} total tracks with genres)")
        
    except Exception as e:
        log(f"  ⚠️  Genre inference error (non-fatal): {e}")
        import traceback
        traceback.print_exc()


def sync_full_library() -> bool:
    """
    Sync full library using spotim8 - updates all parquet files.
    
    Uses incremental sync - only fetches playlists that have changed
    based on Spotify's snapshot_id mechanism.
    
    Updates:
    - playlists.parquet
    - playlist_tracks.parquet  
    - tracks.parquet (with genres column)
    - track_artists.parquet
    - artists.parquet (enhanced with inferred genres)
    """
    log("\n--- Full Library Sync ---")
    
    try:
        # Enable API response caching
        api_cache_dir = DATA_DIR / ".api_cache"
        set_response_cache(api_cache_dir, ttl=3600)
        
        # Initialize client
        sf = Spotim8.from_env(
            progress=True,
            cache=CacheConfig(dir=DATA_DIR)
        )
        
        # Check for existing cached data
        existing_status = sf.status()
        if existing_status.get("playlist_tracks_count", 0) > 0:
            log(f"📦 Found cached data from {existing_status.get('last_sync', 'unknown')}")
            log(f"   • {existing_status.get('playlists_count', 0):,} playlists")
            log(f"   • {existing_status.get('playlist_tracks_count', 0):,} playlist tracks")
            log(f"   • {existing_status.get('tracks_count', 0):,} unique tracks")
            log(f"   • {existing_status.get('artists_count', 0):,} artists")
            log("🔄 Running incremental sync (only changed playlists)...")
        else:
            log("📭 No cached data found - running full sync...")
        
        # Sync library (incremental - only fetches changes based on snapshot_id)
        # Note: We use owned_only=True for playlist_tracks to avoid syncing all followed playlist contents,
        # but we still sync all playlists (owned + followed) metadata so we can learn from their names/descriptions
        with timed_step("Spotify Library Sync (API calls)"):
            stats = sf.sync(
                owned_only=True,  # Only sync tracks from owned playlists (faster)
                include_liked_songs=True
            )
        
        with timed_step("Load All Playlists"):
            # Ensure we have ALL playlists (owned + followed) for genre inference
            # This allows us to learn from followed playlist names/descriptions
            # The sync() call above already loads all playlists, but we ensure they're fresh
            _ = sf.playlists(force=False)  # Load all playlists including followed (uses cache if fresh)
        
        log(f"✅ Library sync complete: {stats}")
        
        # Only regenerate derived tables if something changed
        if stats.get("playlists_updated", 0) > 0 or stats.get("tracks_added", 0) > 0:
            with timed_step("Regenerate Derived Tables"):
                log("🔧 Regenerating derived tables...")
                _ = sf.tracks()
                _ = sf.artists()
                _ = sf.library_wide()
                log("✅ All parquet files updated")
        else:
            log("✅ No changes detected - using cached derived tables")
        
        # Compute track genres with smart caching - only processes changed tracks
        # This dramatically improves sync runtime by avoiding unnecessary computation
        # Skip entirely if all tracks already have genres (common case after initial sync)
        with timed_step("Genre Inference Check"):
            try:
                tracks_check = pd.read_parquet(DATA_DIR / "tracks.parquet")
                tracks_needing = tracks_check[tracks_check["genres"].apply(
                    lambda g: g is None or (isinstance(g, list) and len(g) == 0) or 
                    (pd.api.types.is_scalar(g) and pd.isna(g))
                )]
                if len(tracks_needing) == 0:
                    log("  ⏭️  Skipping genre inference (all tracks already have genres)")
                else:
                    # Check if genre inference is enabled and within limits
                    max_tracks_for_inference = int(os.environ.get("MAX_TRACKS_FOR_INFERENCE", "10000"))
                    enable_inference = _parse_bool_env("ENABLE_GENRE_INFERENCE", True)
                    
                    if not enable_inference:
                        log(f"  ⏭️  Skipping genre inference (disabled via ENABLE_GENRE_INFERENCE)")
                    elif len(tracks_needing) > max_tracks_for_inference:
                        log(f"  ⏭️  Skipping genre inference ({len(tracks_needing):,} tracks need inference - exceeds limit of {max_tracks_for_inference:,})")
                        log(f"      Set MAX_TRACKS_FOR_INFERENCE env var to increase limit")
                    else:
                        # Process genre inference
                        with timed_step("Genre Inference Processing"):
                            log(f"  🔄 Processing genre inference for {len(tracks_needing):,} tracks...")
                            compute_track_genres_incremental(stats)
            except Exception as e:
                # If check fails, skip to avoid blocking
                log(f"  ⏭️  Skipping genre inference (error: {e})")
        
        # Sync export data (Account Data, Extended History, Technical Logs)
        # Wrap in try-except to prevent export data sync from stopping the script
        # Export data sync can be slow or fail on large files, so we make it non-fatal
        with timed_step("Sync Export Data"):
            try:
                log("  🔄 Starting export data sync...")
                sync_export_data()
                log("  ✅ Export data sync completed")
            except KeyboardInterrupt:
                log("  ⚠️  Export data sync interrupted by user")
                raise  # Re-raise to allow proper cleanup
            except Exception as e:
                log(f"  ⚠️  Export data sync error (non-fatal, continuing): {e}")
                import traceback
                log(traceback.format_exc())
                # Continue execution - export data sync is optional
        
        return True
        
    except Exception as e:
        log(f"ERROR: Full library sync failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def sync_export_data() -> bool:
    """
    Sync all Spotify export data (Account Data, Extended History, Technical Logs).
    
    Updates:
    - streaming_history.parquet
    - search_queries.parquet
    - wrapped_data.json
    - follow_data.parquet
    - library_snapshot.parquet
    - playback_errors.parquet
    - playback_retries.parquet
    - webapi_events.parquet
    """
    log("\n--- Export Data Sync ---")
    
    try:
        # Find export folders in data directory
        account_data_dir = DATA_DIR / "Spotify Account Data"
        extended_history_dir = DATA_DIR / "Spotify Extended Streaming History"
        technical_log_dir = DATA_DIR / "Spotify Technical Log Information"
        
        # Check if any export folders exist
        if not any([account_data_dir.exists(), extended_history_dir.exists(), technical_log_dir.exists()]):
            log("ℹ️  No export folders found - skipping export data sync")
            log(f"   Place export folders in {DATA_DIR} to enable:")
            log("   - Spotify Account Data/")
            log("   - Spotify Extended Streaming History/")
            log("   - Spotify Technical Log Information/")
            return True
        
        # Sync all export data
        results = sync_all_export_data(
            account_data_dir=account_data_dir if account_data_dir.exists() else Path("/tmp"),
            extended_history_dir=extended_history_dir if extended_history_dir.exists() else Path("/tmp"),
            technical_log_dir=technical_log_dir if technical_log_dir.exists() else Path("/tmp"),
            data_dir=DATA_DIR,
            force=False
        )
        
        # Log summary
        log("\n📊 Export Data Sync Summary:")
        for key, value in results.items():
            if value is not None and value is not False:
                if isinstance(value, int):
                    log(f"   ✅ {key}: {value:,} records")
                else:
                    log(f"   ✅ {key}: synced")
            else:
                log(f"   ⚠️  {key}: not available")
        
        return True
        
    except Exception as e:
        log(f"❌ Export data sync failed: {e}")
        import traceback
        log(traceback.format_exc())
        return False


# ============================================================================
# PLAYLIST UPDATE FUNCTIONS
# ============================================================================

def rename_playlists_with_old_prefixes(sp: spotipy.Spotify) -> None:
    """Rename playlists that use old prefixes to match new prefix configuration.
    
    This handles migration from old prefix names (e.g., "Auto", "AJAuto") to new
    prefix-based naming (e.g., "Finds", "AJFnds").
    
    Common old prefix patterns:
    - "Auto" -> MONTHLY prefix (e.g., "Fnds")
    - "Top" -> MOST_PLAYED prefix (if changed)
    - "Vibes" -> removed (no longer supported)
    - "OnRepeat" or "Repeat" -> removed (no longer supported)
    - "Discover" or "Discovery" -> DISCOVERY prefix (if changed)
    """
    log("\n--- Renaming Playlists with Old Prefixes ---")
    
    existing = get_existing_playlists(sp, force_refresh=True)
    user = get_user_info(sp)
    user_id = user["id"]
    
    # Build mapping of old prefixes to new prefixes
    # Only include mappings where the prefix actually changed
    old_to_new = {}
    
    # Check "Auto" -> monthly prefix
    if PREFIX_MONTHLY != "Auto" and PREFIX_MONTHLY != "auto":
        old_to_new["Auto"] = PREFIX_MONTHLY
        old_to_new["auto"] = PREFIX_MONTHLY.lower()
        old_to_new["AUTO"] = PREFIX_MONTHLY.upper()
    
    # Check other prefixes if they changed (less common, but handle them)
    if PREFIX_MOST_PLAYED != "Top":
        old_to_new["Top"] = PREFIX_MOST_PLAYED
    # Vibes removed - no longer supported
    # if PREFIX_TIME_BASED != "Vibes":
    #     old_to_new["Vibes"] = PREFIX_TIME_BASED
    # OnRepeat removed - no longer supported
    # if PREFIX_REPEAT not in ["OnRepeat", "Repeat", "Rpt"]:
    #     old_to_new["OnRepeat"] = PREFIX_REPEAT
    #     old_to_new["Repeat"] = PREFIX_REPEAT
    if PREFIX_DISCOVERY not in ["Discover", "Discovery", "Dscvr"]:
        old_to_new["Discover"] = PREFIX_DISCOVERY
        old_to_new["Discovery"] = PREFIX_DISCOVERY
    
    if not old_to_new:
        log("  ℹ️  No prefix changes detected - skipping rename")
        return
    
    renamed_count = 0
    
    for old_name, playlist_id in list(existing.items()):
        new_name = None
        
        # Check each old prefix pattern
        for old_prefix, new_prefix in old_to_new.items():
            # Check if old prefix appears in the name
            if old_prefix in old_name:
                # Try to extract the suffix (date/genre part) and reconstruct
                # Pattern: [Owner][OldPrefix][Suffix]
                # Example: "AJAutoNov24" -> "AJFndsNov24"
                # Example: "AJAutoHipHop" -> "AJFndsHipHop"
                
                # Find where the old prefix starts and ends
                prefix_start = old_name.find(old_prefix)
                if prefix_start == -1:
                    continue
                
                prefix_end = prefix_start + len(old_prefix)
                before_prefix = old_name[:prefix_start]
                suffix = old_name[prefix_end:]
                
                # Reconstruct with new prefix, preserving case
                if old_prefix.isupper():
                    new_prefix_used = new_prefix.upper()
                elif old_prefix.islower():
                    new_prefix_used = new_prefix.lower()
                elif old_prefix[0].isupper():
                    new_prefix_used = new_prefix.title() if len(new_prefix) > 1 else new_prefix.upper()
                else:
                    new_prefix_used = new_prefix
                
                new_name = f"{before_prefix}{new_prefix_used}{suffix}"
                
                # Only rename if the new name is different and doesn't already exist
                if new_name != old_name and new_name not in existing:
                    try:
                        api_call(
                            sp.user_playlist_change_details,
                            user_id,
                            playlist_id,
                            name=new_name
                        )
                        log(f"  ✅ Renamed: '{old_name}' -> '{new_name}'")
                        renamed_count += 1
                        # Invalidate cache so we get fresh data
                        _invalidate_playlist_cache()
                        # Update existing dict for this run
                        existing[new_name] = playlist_id
                        del existing[old_name]
                    except Exception as e:
                        log(f"  ⚠️  Failed to rename '{old_name}': {e}")
                elif new_name in existing:
                    log(f"  ⚠️  Skipped '{old_name}' -> '{new_name}' (target name already exists)")
                break  # Only apply first matching pattern
    
    if renamed_count > 0:
        log(f"  ✅ Renamed {renamed_count} playlist(s)")
    else:
        log("  ℹ️  No playlists needed renaming")


def fix_incorrectly_named_yearly_genre_playlists(sp: spotipy.Spotify) -> None:
    """Fix yearly genre playlists that were incorrectly named using GENRE_MONTHLY_TEMPLATE.
    
    This fixes playlists that were created with the monthly template (which includes {mon})
    but should have been created with the yearly template (which doesn't include {mon}).
    The wrong names might have literal template placeholders like {mon}, {year}, etc.
    """
    log("\n--- Fixing Incorrectly Named Yearly Genre Playlists ---")
    
    existing = get_existing_playlists(sp, force_refresh=True)
    user = get_user_info(sp)
    user_id = user["id"]
    
    renamed_count = 0
    template_placeholders = ["{mon}", "{year}", "{prefix}", "{genre}", "{owner}"]
    
    for old_name, playlist_id in list(existing.items()):
        # Check if name contains literal template placeholders (definitely wrong)
        if any(placeholder in old_name for placeholder in template_placeholders):
            log(f"  ⚠️  Found playlist with template placeholders: '{old_name}'")
            log(f"      This playlist needs manual fixing - cannot determine correct name automatically")
            # We can't automatically fix these without knowing the intended year/genre
            continue
    
    if renamed_count > 0:
        log(f"  ✅ Fixed {renamed_count} incorrectly named playlist(s)")
    else:
        log("  ℹ️  No incorrectly named playlists found (or manual fix needed)")


def update_monthly_playlists(sp: spotipy.Spotify, keep_last_n_months: int = 3) -> dict:
    """Update monthly playlists for all types (Finds, Discover).
    
    Only creates/updates monthly playlists for the last N months (default: 3).
    Older months are automatically consolidated into yearly playlists.
    
    Data Sources:
    - "Finds" playlists: Use API data (liked songs) - always up-to-date
    - Top and Discovery playlists: Use streaming history from exports (Vibes/OnRepeat removed)
      - Streaming history is updated periodically and may lag behind API data
      - Recent months may be incomplete if export is outdated
      - Missing history results in empty playlists for those types
    
    Args:
        keep_last_n_months: Number of recent months to keep as monthly playlists (default: 3)
    
    Note: This function only ADDS tracks to playlists. It never removes tracks.
    Manually added tracks are preserved and will remain in the playlists.
    """
    log(f"\n--- Monthly Playlists (Last {keep_last_n_months} Months Only) ---")
    
    # Log enabled playlist types
    # NOTE: Only "Finds" playlists are created monthly. Top/Dscvr are yearly only.
    enabled_types = []
    if ENABLE_MONTHLY:
        enabled_types.append("Finds (monthly)")
    if ENABLE_MOST_PLAYED:
        enabled_types.append("Top (yearly only)")
    # Vbz/Rpt removed - only Top and Discovery kept for yearly
    # if ENABLE_TIME_BASED:
    #     enabled_types.append("Vbz (yearly only)")
    # if ENABLE_REPEAT:
    #     enabled_types.append("Rpt (yearly only)")
    if ENABLE_DISCOVERY:
        enabled_types.append("Dscvr (yearly only)")
    
    if enabled_types:
        log(f"  Enabled playlist types: {', '.join(enabled_types)}")
        log(f"  📌 Note: Top/Dscvr are created as yearly playlists only (no monthly). Vbz/Rpt removed.")
    else:
        log("  ⚠️  No playlist types enabled - check .env file")
        return {}
    
    # Load streaming history for Top/Vibes/OnRepeat/Discover playlists
    # NOTE: Streaming history comes from periodic Spotify exports and may lag behind API data.
    # API data (liked songs) is always more up-to-date than streaming history exports.
    # If streaming history is missing or incomplete, these playlist types will be empty or incomplete.
    from spotim8.streaming_history import load_streaming_history
    history_df = load_streaming_history(DATA_DIR)
    if history_df is not None and not history_df.empty:
        # Ensure timestamp is datetime
        if 'timestamp' in history_df.columns:
            history_df['timestamp'] = pd.to_datetime(history_df['timestamp'], errors='coerce', utc=True)
        
        # Check data freshness - warn if streaming history is significantly behind
        # Streaming history comes from periodic exports, so it may lag behind API data
        if 'timestamp' in history_df.columns:
            try:
                latest_history = history_df['timestamp'].max()
                if pd.notna(latest_history):
                    # Convert to naive datetime for comparison if needed
                    if latest_history.tzinfo:
                        latest_naive = latest_history.replace(tzinfo=None)
                        now = datetime.now()
                    else:
                        latest_naive = latest_history
                        now = datetime.now()
                    
                    days_behind = (now - latest_naive).days
                    if days_behind > 30:
                        latest_str = latest_history.strftime('%Y-%m-%d') if hasattr(latest_history, 'strftime') else str(latest_history)
                        log(f"  ⚠️  Streaming history is {days_behind} days old (latest: {latest_str})")
                        log(f"      Recent months may be incomplete. Export new data for up-to-date playlists.")
            except Exception:
                pass  # Skip freshness check if there's an error
        
        log(f"  Loaded streaming history: {len(history_df):,} records")
    else:
        log("  ⚠️  No streaming history found - Discovery playlists will be empty")
        log("      Export streaming history data to enable these playlist types")
    
    # Load liked songs data for "Finds" playlists (API data only - never uses streaming history)
    playlist_tracks_path = DATA_DIR / "playlist_tracks.parquet"
    all_month_to_tracks = {}
    
    if playlist_tracks_path.exists():
        library = pd.read_parquet(playlist_tracks_path)
        liked = library[library["playlist_id"].astype(str) == LIKED_SONGS_PLAYLIST_ID].copy()
        
        if not liked.empty:
            # Parse timestamps
            added_col = None
            for col in ["added_at", "playlist_added_at", "track_added_at"]:
                if col in liked.columns:
                    added_col = col
                    break
            
            if added_col:
                liked[added_col] = pd.to_datetime(liked[added_col], errors="coerce", utc=True)
                liked["month"] = liked[added_col].dt.to_period("M").astype(str)
                
                # Handle both track_uri and track_id columns
                if "track_uri" in liked.columns:
                    liked["_uri"] = liked["track_uri"]
                else:
                    liked["_uri"] = liked["track_id"].map(_to_uri)
                
                # Build month -> tracks mapping for "Finds" playlists (API data only)
                for month, group in liked.groupby("month"):
                    uris = group["_uri"].dropna().tolist()
                    seen = set()
                    unique = [u for u in uris if not (u in seen or seen.add(u))]
                    all_month_to_tracks[month] = {"monthly": unique}
                
                log(f"  Loaded liked songs (API data) for 'Finds' playlists: {len(all_month_to_tracks)} month(s)")
        else:
            log("  ⚠️  No liked songs found in library data - 'Finds' playlists will be empty")
    else:
        log("  ⚠️  Library data not found - 'Finds' playlists will be empty (run full sync first)")
    
    # Get months for "Finds" playlists (API data only - liked songs)
    finds_months = set(all_month_to_tracks.keys())
    
    # Get months for other playlist types (streaming history)
    history_months = set()
    if history_df is not None and not history_df.empty:
        history_df['month'] = history_df['timestamp'].dt.to_period('M').astype(str)
        history_months = set(history_df['month'].unique())
    
    # For "Finds" playlists, only use months from API data (liked songs)
    # For Discovery playlists, use months from streaming history (Top/Vibes removed)
    # Combine for processing, but "Finds" will only use API data
    all_months = finds_months | history_months
    
    # Filter to only the last N months
    if all_months:
        sorted_months = sorted(all_months)
        recent_months = sorted_months[-keep_last_n_months:]
        older_months = [m for m in sorted_months if m not in recent_months]
        if older_months:
            log(f"📅 Keeping {len(recent_months)} recent months as monthly playlists: {', '.join(recent_months)}")
            log(f"📦 {len(older_months)} older months will be consolidated into yearly playlists")
            if finds_months:
                finds_recent = [m for m in recent_months if m in finds_months]
                log(f"   📌 'Finds' playlists will use API data (liked songs) for {len(finds_recent)} month(s)")
    else:
        recent_months = []
    
    if not recent_months:
        log("No months to process")
        return {}
    
    log(f"Processing {len(recent_months)} month(s) for all playlist types...")
    
    # Get existing playlists (cached)
    existing = get_existing_playlists(sp)
    user = get_user_info(sp)
    user_id = user["id"]
    
    # Define playlist types and their configurations
    # "Finds" playlists use API data (liked songs) only - never streaming history
    # Other playlists use streaming history data
    # Only include playlist types that are enabled in .env
    # NOTE: Dscvr is created as yearly playlists only (no monthly). Top/Vbz/Rpt removed.
    # Only "Finds" playlists are created monthly
    playlist_configs = []
    
    if ENABLE_MONTHLY:
        playlist_configs.append((
            "monthly", MONTHLY_NAME_TEMPLATE, "Liked songs", 
            lambda m: all_month_to_tracks.get(m, {}).get("monthly", [])  # API data only
        ))
    
    # Top/Vbz/Rpt/Dscvr are NOT created as monthly playlists - only yearly
    # They are created in consolidate_old_monthly_playlists() for all years with streaming history
    
    if not playlist_configs:
        log("⚠️  All playlist types are disabled in .env file. No playlists will be created.")
        return {}
    
    month_to_tracks = {}
    
    for month in sorted(recent_months):
        month_to_tracks[month] = {}
        
        for playlist_type, template, description, get_tracks_fn in playlist_configs:
            # Get tracks for this playlist type and month
            track_uris = get_tracks_fn(month)
            
            if not track_uris:
                continue
            
            month_to_tracks[month][playlist_type] = track_uris
            
            # Format playlist name (all types use monthly format for monthly playlists)
            name = format_playlist_name(template, month, playlist_type=playlist_type)
            
            # Check for duplicate
            if name in existing:
                pid = existing[name]
                already = get_playlist_tracks(sp, pid)
                to_add = [u for u in track_uris if u not in already]
                
                if to_add:
                    for chunk in _chunked(to_add, 50):
                        api_call(sp.playlist_add_items, pid, chunk)
                    if pid in _playlist_tracks_cache:
                        del _playlist_tracks_cache[pid]
                    log(f"  {name}: +{len(to_add)} tracks ({len(track_uris)} total)")
                else:
                    log(f"  {name}: up to date ({len(track_uris)} tracks)")
            else:
                # Calculate last date of the month for creation date reference
                from calendar import monthrange
                year, month_num = map(int, month.split("-"))
                last_day = monthrange(year, month_num)[1]
                created_at = datetime(year, month_num, last_day, 23, 59, 59)
                
                # Create playlist
                pl = api_call(
                    sp.user_playlist_create,
                    user_id,
                    name,
                    public=False,
                    description=format_playlist_description(description, period=month, playlist_type=playlist_type),
                )
                pid = pl["id"]
                
                # Add tracks
                for chunk in _chunked(track_uris, 50):
                    api_call(sp.playlist_add_items, pid, chunk)
                
                _invalidate_playlist_cache()
                log(f"  {name}: created with {len(track_uris)} tracks")
    
    return month_to_tracks


def get_most_played_tracks(history_df: pd.DataFrame, month_str: str = None, limit: int = 50) -> list:
    """
    Get most played tracks for a given month (or all data if month_str is None) from streaming history.
    
    Args:
        history_df: Streaming history DataFrame
        month_str: Month string like '2025-01' (None to use all data)
        limit: Maximum number of tracks to return
    
    Returns:
        List of track URIs (most played first)
    """
    if history_df is None or history_df.empty:
        return []
    
    # Filter to month if provided
    if month_str:
        month_data = history_df.copy()
        month_data['month'] = month_data['timestamp'].dt.to_period('M').astype(str)
        month_data = month_data[month_data['month'] == month_str].copy()
    else:
        month_data = history_df.copy()
    
    if month_data.empty:
        return []
    
    # Group by track URI and sum play counts and duration
    if 'track_uri' in month_data.columns:
        track_col = 'track_uri'
    elif 'spotify_track_uri' in month_data.columns:
        track_col = 'spotify_track_uri'
    else:
        # Try to construct from track name/artist (less reliable)
        return []
    
    # Count plays and sum duration
    track_stats = month_data.groupby(track_col).agg({
        'ms_played': ['count', 'sum']
    }).reset_index()
    track_stats.columns = ['track_uri', 'play_count', 'total_ms']
    
    # Sort by play count (primary) and total duration (secondary)
    track_stats = track_stats.sort_values(['play_count', 'total_ms'], ascending=False)
    
    # Get top tracks
    top_tracks = track_stats.head(limit)['track_uri'].tolist()
    
    # Filter out None/NaN values
    return [uri for uri in top_tracks if pd.notna(uri) and uri]


def get_time_based_tracks(history_df: pd.DataFrame, month_str: str = None, time_type: str = "morning", limit: int = 50) -> list:
    """
    Get tracks played at specific times for a given month (or all data if month_str is None).
    
    Args:
        history_df: Streaming history DataFrame
        month_str: Month string like '2025-01' (None to use all data)
        time_type: "morning" (6-11), "afternoon" (12-17), "evening" (18-23), "night" (0-5), "weekend"
        limit: Maximum number of tracks to return
    
    Returns:
        List of track URIs
    """
    if history_df is None or history_df.empty:
        return []
    
    # Filter to month if provided
    if month_str:
        history_df = history_df.copy()
        history_df['month'] = history_df['timestamp'].dt.to_period('M').astype(str)
        month_data = history_df[history_df['month'] == month_str].copy()
    else:
        month_data = history_df.copy()
    
    if month_data.empty:
        return []
    
    # Filter by time
    if time_type == "morning":
        filtered = month_data[(month_data['hour'] >= 6) & (month_data['hour'] < 12)]
    elif time_type == "afternoon":
        filtered = month_data[(month_data['hour'] >= 12) & (month_data['hour'] < 18)]
    elif time_type == "evening":
        filtered = month_data[(month_data['hour'] >= 18) & (month_data['hour'] < 24)]
    elif time_type == "night":
        filtered = month_data[(month_data['hour'] >= 0) & (month_data['hour'] < 6)]
    elif time_type == "weekend":
        filtered = month_data[month_data['day_of_week_num'].isin([5, 6])]  # Sat, Sun
    else:
        return []
    
    if filtered.empty:
        return []
    
    # Get track URI column
    if 'track_uri' in filtered.columns:
        track_col = 'track_uri'
    elif 'spotify_track_uri' in filtered.columns:
        track_col = 'spotify_track_uri'
    else:
        return []
    
    # Get most played tracks for this time period
    track_stats = filtered.groupby(track_col).agg({
        'ms_played': ['count', 'sum']
    }).reset_index()
    track_stats.columns = ['track_uri', 'play_count', 'total_ms']
    track_stats = track_stats.sort_values(['play_count', 'total_ms'], ascending=False)
    
    top_tracks = track_stats.head(limit)['track_uri'].tolist()
    return [uri for uri in top_tracks if pd.notna(uri) and uri]


def get_repeat_tracks(history_df: pd.DataFrame, month_str: str = None, min_repeats: int = 3, limit: int = 50) -> list:
    """
    Get tracks that were played multiple times (on repeat) in a given month (or all data if month_str is None).
    
    Args:
        history_df: Streaming history DataFrame
        month_str: Month string like '2025-01' (None to use all data)
        min_repeats: Minimum number of plays to be considered "on repeat"
        limit: Maximum number of tracks to return
    
    Returns:
        List of track URIs
    """
    if history_df is None or history_df.empty:
        return []
    
    # Filter to month if provided
    if month_str:
        history_df = history_df.copy()
        history_df['month'] = history_df['timestamp'].dt.to_period('M').astype(str)
        month_data = history_df[history_df['month'] == month_str].copy()
    else:
        month_data = history_df.copy()
    
    if month_data.empty:
        return []
    
    # Get track URI column
    if 'track_uri' in month_data.columns:
        track_col = 'track_uri'
    elif 'spotify_track_uri' in month_data.columns:
        track_col = 'spotify_track_uri'
    else:
        return []
    
    # Count plays per track
    play_counts = month_data.groupby(track_col).size().reset_index(name='play_count')
    
    # Filter to tracks played at least min_repeats times
    repeat_tracks = play_counts[play_counts['play_count'] >= min_repeats].copy()
    
    # Sort by play count (most repeated first)
    repeat_tracks = repeat_tracks.sort_values('play_count', ascending=False)
    
    # Get top tracks
    top_tracks = repeat_tracks.head(limit)[track_col].tolist()
    return [uri for uri in top_tracks if pd.notna(uri) and uri]


def get_discovery_tracks(history_df: pd.DataFrame, month_str: str = None, limit: int = 50) -> list:
    """
    Get newly discovered tracks (first time played) in a given month (or all data if month_str is None).
    
    Args:
        history_df: Streaming history DataFrame
        month_str: Month string like '2025-01' (None to use all data - finds first plays overall)
        limit: Maximum number of tracks to return
    
    Returns:
        List of track URIs
    """
    if history_df is None or history_df.empty:
        return []
    
    # Get track URI column
    if 'track_uri' in history_df.columns:
        track_col = 'track_uri'
    elif 'spotify_track_uri' in history_df.columns:
        track_col = 'spotify_track_uri'
    else:
        return []
    
    # Filter to month if provided
    if month_str:
        history_df = history_df.copy()
        history_df['month'] = history_df['timestamp'].dt.to_period('M').astype(str)
        month_data = history_df[history_df['month'] == month_str].copy()
        
        if month_data.empty:
            return []
        
        # Get all tracks played before this month
        before_month = history_df[history_df['month'] < month_str]
        known_tracks = set()
        if not before_month.empty and track_col in before_month.columns:
            known_tracks = set(before_month[track_col].dropna().unique())
        
        # Get tracks played in this month that weren't played before
        month_tracks = month_data[track_col].dropna().unique()
        new_tracks = [uri for uri in month_tracks if uri not in known_tracks]
        
        # Sort by first play time (earliest discoveries first)
        if new_tracks:
            first_plays = month_data[month_data[track_col].isin(new_tracks)].groupby(track_col)['timestamp'].min().reset_index()
            first_plays = first_plays.sort_values('timestamp')
            new_tracks = first_plays.head(limit)[track_col].tolist()
        
        return [uri for uri in new_tracks if pd.notna(uri) and uri]
    else:
        # No month specified - get first plays overall (sorted by first play time)
        first_plays = history_df.groupby(track_col)['timestamp'].min().reset_index()
        first_plays = first_plays.sort_values('timestamp')
        new_tracks = first_plays.head(limit)[track_col].tolist()
        return [uri for uri in new_tracks if pd.notna(uri) and uri]


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
        else:
            log(f"  {playlist_name}: up to date ({len(track_uris)} tracks)")
        return pid
    else:
        # Calculate period end date (for reference, Spotify API doesn't support setting it)
        period_end = None
        if period_value:
            from calendar import monthrange
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
        
        # Invalidate cache
        _invalidate_playlist_cache()
        log(f"  {playlist_name}: created with {len(track_uris)} tracks")
        return pid


def consolidate_old_monthly_playlists(sp: spotipy.Spotify, keep_last_n_months: int = 3) -> None:
    """Consolidate monthly playlists older than the last N months into yearly playlists.
    
    Only keeps the last N months (default: 3) as monthly playlists.
    For any months older than that:
    - Combine all monthly playlists from each year (e.g., AJFindsJan22, AJFindsFeb22, ...) 
      into yearly playlists for all enabled types
    - Delete the old monthly playlists
    
    Data Sources:
    - "Finds" playlists: Use API data (liked songs) - always up-to-date
    - Top and Discovery playlists: Use streaming history from exports (Vibes/OnRepeat removed)
      - Creates yearly playlists for ALL years with streaming history data
      - Streaming history may be incomplete for recent months (exports lag behind API)
      - Missing history for a year results in empty playlists for those types
    
    Args:
        keep_last_n_months: Number of recent months to keep as monthly playlists (default: 3)
    
    Note: This function only ADDS tracks to existing yearly playlists. It never removes tracks.
    Manually added tracks are preserved and will remain in the playlists.
    """
    log("\n--- Consolidating Old Monthly Playlists (Older than Last 3 Months) ---")
    
    # Calculate cutoff date (keep last N months)
    # We want to keep the last N months, so anything at or before (current - N months) should be consolidated
    # Example: If current is Jan 2026 and N=3, keep Nov 2025, Dec 2025, Jan 2026
    # So cutoff should be Oct 2025 (last month to consolidate)
    cutoff_date = datetime.now() - relativedelta(months=keep_last_n_months)
    cutoff_year_month = cutoff_date.strftime("%Y-%m")
    
    # Get all existing playlists (cached)
    existing = get_existing_playlists(sp)
    user = get_user_info(sp)
    user_id = user["id"]
    
    # Pattern: {owner}{prefix}{mon}{year} e.g., "AJFindsJan23", "AJTopJan23", etc.
    # Extract monthly playlists matching patterns for enabled playlist types only
    # NOTE: Only monthly (Finds), Top, and Discovery are kept for yearly consolidation
    playlist_types = {}
    if ENABLE_MONTHLY:
        playlist_types["monthly"] = PREFIX_MONTHLY
    if ENABLE_MOST_PLAYED:
        playlist_types["most_played"] = PREFIX_MOST_PLAYED
    # Vibes/OnRepeat removed - only Top and Discovery kept for yearly
    # if ENABLE_TIME_BASED:
    #     playlist_types["time_based"] = PREFIX_TIME_BASED
    # if ENABLE_REPEAT:
    #     playlist_types["repeat"] = PREFIX_REPEAT
    if ENABLE_DISCOVERY:
        playlist_types["discovery"] = PREFIX_DISCOVERY
    
    monthly_playlists = {}  # {year: {type: [(name, id), ...]}}
    
    for playlist_name, playlist_id in existing.items():
        # Check each playlist type
        for playlist_type, prefix in playlist_types.items():
            monthly_pattern = f"{OWNER_NAME}{prefix}"
            if playlist_name.startswith(monthly_pattern):
                # Check if it matches monthly format (has a month name)
                for mon_abbr in MONTH_NAMES.values():
                    if playlist_name.startswith(f"{monthly_pattern}{mon_abbr}"):
                        # Extract year (2 or 4 digits at the end)
                        remaining = playlist_name[len(f"{monthly_pattern}{mon_abbr}"):]
                        if remaining.isdigit():
                            year_str = remaining
                            # Convert 2-digit year to 4-digit (assume 2000s)
                            if len(year_str) == 2:
                                year = 2000 + int(year_str)
                            else:
                                year = int(year_str)
                            
                            # Find the month number from abbreviation
                            month_num = None
                            for num, abbr in MONTH_NAMES.items():
                                if abbr == mon_abbr:
                                    month_num = num
                                    break
                            
                            if month_num:
                                # Create YYYY-MM format string
                                month_str = f"{year}-{month_num}"
                                
                                # Check if this month is at or before cutoff (should be consolidated)
                                # Use <= to include the cutoff month itself
                                if month_str <= cutoff_year_month:
                                    if year not in monthly_playlists:
                                        monthly_playlists[year] = {}
                                    if playlist_type not in monthly_playlists[year]:
                                        monthly_playlists[year][playlist_type] = []
                                    monthly_playlists[year][playlist_type].append((playlist_name, playlist_id))
                        break
                break  # Found matching type, no need to check others
    
    # Load liked songs data to get tracks by year (for "Finds" playlists)
    year_to_tracks = {}
    try:
        playlist_tracks_path = DATA_DIR / "playlist_tracks.parquet"
        if playlist_tracks_path.exists():
            library = pd.read_parquet(playlist_tracks_path)
            liked = library[library["playlist_id"].astype(str) == LIKED_SONGS_PLAYLIST_ID].copy()
            
            if not liked.empty:
                # Parse timestamps
                added_col = None
                for col in ["added_at", "playlist_added_at", "track_added_at"]:
                    if col in liked.columns:
                        added_col = col
                        break
                
                if added_col:
                    liked[added_col] = pd.to_datetime(liked[added_col], errors="coerce", utc=True)
                    liked["year"] = liked[added_col].dt.year
                    
                    # Handle both track_uri and track_id columns
                    if "track_uri" in liked.columns:
                        liked["_uri"] = liked["track_uri"]
                    else:
                        liked["_uri"] = liked["track_id"].map(_to_uri)
                    
                    # Build year -> tracks mapping (only for months at or before cutoff)
                    liked["year_month"] = liked[added_col].dt.to_period("M").astype(str)
                    for year_month, group in liked.groupby("year_month"):
                        if year_month <= cutoff_year_month:
                            year = int(year_month.split("-")[0])
                            uris = group["_uri"].dropna().tolist()
                            # Deduplicate while preserving order
                            seen = set()
                            unique = [u for u in uris if not (u in seen or seen.add(u))]
                            if year not in year_to_tracks:
                                year_to_tracks[year] = []
                            year_to_tracks[year].extend(unique)
                    
                    # Deduplicate tracks per year
                    for year in year_to_tracks:
                        seen = set()
                        year_to_tracks[year] = [u for u in year_to_tracks[year] if not (u in seen or seen.add(u))]
    except Exception as e:
        log(f"  ⚠️  Could not load liked songs data: {e}")
    
    # Load streaming history for Top and Discovery playlists (Vibes/OnRepeat removed from yearly)
    # NOTE: Streaming history comes from periodic Spotify exports and may lag behind API data.
    # This is used for creating yearly playlists for previous years.
    # Missing or incomplete history will result in empty playlists for those years.
    from spotim8.streaming_history import load_streaming_history
    history_df = load_streaming_history(DATA_DIR)
    year_to_tracks_history = {}  # {year: {type: [uris]}}
    
    if history_df is not None and not history_df.empty:
        try:
            history_df['timestamp'] = pd.to_datetime(history_df['timestamp'], errors='coerce', utc=True)
            history_df['year'] = history_df['timestamp'].dt.year
            history_df['year_month'] = history_df['timestamp'].dt.to_period('M').astype(str)
            
            # Get track URI column
            track_col = None
            if 'track_uri' in history_df.columns:
                track_col = 'track_uri'
            elif 'spotify_track_uri' in history_df.columns:
                track_col = 'spotify_track_uri'
            
            if track_col:
                # Get ALL years from streaming history (not just old months)
                # Top/Dscvr are created as yearly playlists only (no monthly). Vbz/Rpt removed.
                for year in history_df['year'].unique():
                    year_data = history_df[history_df['year'] == year].copy()
                    if year not in year_to_tracks_history:
                        year_to_tracks_history[year] = {}
                    
                    # Most played tracks for the year - KEPT for yearly playlists
                    top_tracks = get_most_played_tracks(year_data, None, limit=100)
                    if top_tracks:
                        year_to_tracks_history[year]['most_played'] = top_tracks
                    
                    # Repeat tracks removed - OnRepeat no longer supported
                    # repeat_tracks = get_repeat_tracks(year_data, None, min_repeats=3, limit=100)
                    # if repeat_tracks:
                    #     year_to_tracks_history[year]['repeat'] = repeat_tracks
                    
                    # Discovery tracks (first time played in this year) - KEPT for yearly playlists
                    discovery_tracks = get_discovery_tracks(year_data, None, limit=100)
                    if discovery_tracks:
                        year_to_tracks_history[year]['discovery'] = discovery_tracks
                    
                    # Time-based tracks removed - Vibes no longer in yearly playlists
                    # time_tracks = get_time_based_tracks(year_data, None, time_type="evening", limit=100)
                    # if time_tracks:
                    #     year_to_tracks_history[year]['time_based'] = time_tracks
        except Exception as e:
            log(f"  ⚠️  Could not process streaming history for consolidation: {e}")
    
    # Consolidate years that have:
    # 1. Monthly playlists that need consolidation (for "Finds" only), OR
    # 2. Streaming history data (for Dscvr - yearly only), OR
    # 3. Liked songs data (for Finds - yearly)
    # NOTE: Dscvr is created as yearly playlists only (no monthly). Top/Vbz/Rpt removed.
    years_to_consolidate = set()
    
    # Get all years from all data sources
    all_years = set(monthly_playlists.keys()) | set(year_to_tracks.keys()) | set(year_to_tracks_history.keys())
    
    # Check which years need consolidation (for all playlist types)
    for year in sorted(all_years):
        year_short = str(year)[2:] if len(str(year)) == 4 else str(year)
        needs_consolidation = False
        
        # Check if "Finds" monthly playlists need consolidation
        if year in monthly_playlists and monthly_playlists[year]:
            needs_consolidation = True
        
        # Check if yearly playlists need to be created for Top and Discovery (Vbz/Rpt removed)
        # Top and Discovery are created as yearly playlists only (no monthly)
        if year in year_to_tracks_history:
            for playlist_type in ["most_played", "discovery"]:  # Top and Discovery kept for yearly
                if playlist_type in year_to_tracks_history[year]:
                    # Check if this playlist type is enabled
                    if (playlist_type == "most_played" and ENABLE_MOST_PLAYED) or \
                       (playlist_type == "discovery" and ENABLE_DISCOVERY):
                        # Check if yearly playlist exists
                        yearly_name = format_playlist_name(YEARLY_NAME_TEMPLATE, year=year_short, playlist_type=playlist_type)
                        if yearly_name not in existing:
                            needs_consolidation = True
                            break
        
        # Check if "Finds" yearly playlist needs to be created (from liked songs data)
        if year in year_to_tracks and year_to_tracks[year]:
            yearly_name = format_yearly_playlist_name(str(year))
            if yearly_name not in existing:
                needs_consolidation = True
        
        if needs_consolidation:
            years_to_consolidate.add(year)
    
    if not years_to_consolidate:
        log("  No old years need consolidation (all already consolidated)")
        return
    
    log(f"  Found {len(years_to_consolidate)} year(s) to consolidate: {sorted(years_to_consolidate)}")
    
    # Log which data sources are available for each year
    for year in sorted(years_to_consolidate):
        sources = []
        if year in monthly_playlists:
            sources.append(f"{len(monthly_playlists[year])} monthly playlist(s)")
        if year in year_to_tracks:
            sources.append("liked songs data")
        if year in year_to_tracks_history:
            enabled_types = [t for t in year_to_tracks_history[year].keys() if t in playlist_types]
            if enabled_types:
                sources.append(f"streaming history ({', '.join(enabled_types)})")
        if sources:
            log(f"    {year}: {', '.join(sources)}")
    
    # Load genre data for genre splits
    track_to_genres = {}  # Map URI to list of genres (tracks can have multiple)
    try:
        # Try to use stored track genres first (most efficient)
        tracks_df = pd.read_parquet(DATA_DIR / "tracks.parquet")
        if "genres" in tracks_df.columns:
            # Use stored track genres
            for _, track_row in tracks_df.iterrows():
                track_id = track_row["track_id"]
                uri = f"spotify:track:{track_id}"
                stored_genres = _parse_genres(track_row.get("genres"))
                if stored_genres:
                    # Convert stored genres to split genres
                    split_genres = get_all_split_genres(stored_genres)
                    if split_genres:
                        track_to_genres[uri] = split_genres
        
        track_artists = pd.read_parquet(DATA_DIR / "track_artists.parquet")
        artists = pd.read_parquet(DATA_DIR / "artists.parquet")
        artist_genres_map = artists.set_index("artist_id")["genres"].to_dict()
        
        # Build track -> genre mapping for all tracks we might need
        all_track_uris = set()
        for year in years_to_consolidate:
            if year in year_to_tracks:
                all_track_uris.update(year_to_tracks[year])
            if year in monthly_playlists:
                # Handle nested structure: {year: {type: [(name, id), ...]}}
                for playlist_type, playlists in monthly_playlists[year].items():
                    for _, pid in playlists:
                        all_track_uris.update(get_playlist_tracks(sp, pid))
        
        track_ids = {u.split(":")[-1] for u in all_track_uris if u.startswith("spotify:track:")}
        
        # Fill in missing genres using artist data
        for track_id in track_ids:
            uri = f"spotify:track:{track_id}"
            if uri in track_to_genres:
                continue  # Already have genres from stored data
            
            # Get all genres from all artists on this track
            all_track_genres = _get_all_track_genres(track_id, track_artists, artist_genres_map)
            split_genres = get_all_split_genres(all_track_genres)
            if split_genres:
                track_to_genres[uri] = split_genres
    except Exception as e:
        log(f"  ⚠️  Could not load genre data: {e}")
        log(f"  Will create main playlists only (no genre splits)")
    
    # For each old year, consolidate into yearly playlists for each type
    for year in sorted(years_to_consolidate):
        year_short = str(year)[2:] if len(str(year)) == 4 else str(year)
        
        # Process each playlist type
        for playlist_type, prefix in playlist_types.items():
            # Collect all tracks for this year and type
            # Use list to preserve ordering for "Top" and other ordered playlists
            all_tracks_list = []
            all_tracks_set = set()  # For deduplication
            
            # First, try to get tracks from existing monthly playlists of this type
            if year in monthly_playlists and playlist_type in monthly_playlists[year]:
                for monthly_name, monthly_id in monthly_playlists[year][playlist_type]:
                    tracks = get_playlist_tracks(sp, monthly_id)
                    # Preserve order from playlist (playlists are already ordered)
                    for track in tracks:
                        if track not in all_tracks_set:
                            all_tracks_list.append(track)
                            all_tracks_set.add(track)
                    log(f"    - {monthly_name}: {len(tracks)} tracks")
            
            # If no tracks from playlists, use appropriate data source
            if not all_tracks_list:
                if playlist_type == "monthly" and year in year_to_tracks:
                    # Use liked songs data for "Finds" playlists
                    for track in year_to_tracks[year]:
                        if track not in all_tracks_set:
                            all_tracks_list.append(track)
                            all_tracks_set.add(track)
                    log(f"    - Using liked songs data for {playlist_type}: {len(year_to_tracks[year])} tracks")
                elif playlist_type in ["most_played", "discovery"]:  # Top and Discovery kept (time_based/repeat removed)
                    # Use streaming history data (already sorted)
                    if year in year_to_tracks_history and playlist_type in year_to_tracks_history[year]:
                        # These are already sorted by the get_*_tracks functions
                        for track in year_to_tracks_history[year][playlist_type]:
                            if track not in all_tracks_set:
                                all_tracks_list.append(track)
                                all_tracks_set.add(track)
                        log(f"    - Using streaming history for {playlist_type}: {len(year_to_tracks_history[year][playlist_type])} tracks")
            
            # Re-sort tracks by play count if we got them from monthly playlists
            # Note: If tracks came from year_to_tracks_history, they're already sorted, so we skip re-sorting
            tracks_from_monthly = year in monthly_playlists and playlist_type in monthly_playlists.get(year, {})
            if all_tracks_list and playlist_type in ["most_played", "discovery"] and tracks_from_monthly:
                # If we have streaming history for this year, re-sort by actual play counts
                if history_df is not None and not history_df.empty:
                    try:
                        # Filter to this year's data
                        year_data = history_df[history_df['year'] == year].copy()
                        if not year_data.empty:
                            # Get track URI column
                            track_col = None
                            if 'track_uri' in year_data.columns:
                                track_col = 'track_uri'
                            elif 'spotify_track_uri' in year_data.columns:
                                track_col = 'spotify_track_uri'
                            
                            if track_col:
                                # Calculate play counts for all tracks
                                track_stats = year_data.groupby(track_col).agg({
                                    'ms_played': ['count', 'sum']
                                }).reset_index()
                                track_stats.columns = ['track_uri', 'play_count', 'total_ms']
                                
                                # Create a mapping of track URI to play count
                                play_count_map = dict(zip(track_stats['track_uri'], track_stats['play_count']))
                                
                                # Sort tracks by play count (most played first)
                                # Tracks not in history get play_count = 0
                                if playlist_type == "most_played":
                                    all_tracks_list.sort(
                                        key=lambda uri: (play_count_map.get(uri, 0), 0),
                                        reverse=True
                                    )
                                    log(f"    - Re-sorted {playlist_type} tracks by play count")
                                # Discovery tracks are already sorted by first play time (most recent first)
                                # from get_discovery_tracks, so we keep that order
                    except Exception as e:
                        log(f"    ⚠️  Could not re-sort tracks by play count: {e}")
                        # Continue with existing order if sorting fails
            
            if not all_tracks_list:
                log(f"    ⚠️  No tracks found for {year} ({playlist_type}), skipping")
                continue
            
            # Create yearly playlist for this type
            if playlist_type == "monthly":
                # For monthly type, create main + 3 genre splits
                main_playlist_name = format_yearly_playlist_name(str(year))
                playlist_configs = [
                    (main_playlist_name, "All tracks", None),
                    (format_playlist_name(GENRE_YEARLY_TEMPLATE, genre="HipHop", year=year_short, playlist_type="genre_monthly"), "Hip Hop tracks", "HipHop"),
                    (format_playlist_name(GENRE_YEARLY_TEMPLATE, genre="Dance", year=year_short, playlist_type="genre_monthly"), "Dance tracks", "Dance"),
                    (format_playlist_name(GENRE_YEARLY_TEMPLATE, genre="Other", year=year_short, playlist_type="genre_monthly"), "Other tracks", "Other"),
                ]
            else:
                # For other types, create single yearly playlist
                # Use yearly template format (no month) for yearly playlists
                # The templates default to monthly format, so we use YEARLY_NAME_TEMPLATE as base
                # but with the appropriate prefix for each type
                yearly_name = format_playlist_name(YEARLY_NAME_TEMPLATE, year=year_short, playlist_type=playlist_type)
                playlist_configs = [
                    (yearly_name, f"{playlist_type.replace('_', ' ').title()} tracks", None),
                ]
            
            for playlist_name, description, genre_filter in playlist_configs:
                # Filter tracks by genre if needed (tracks can match multiple genres)
                if genre_filter:
                    filtered_tracks = [
                        u for u in all_tracks_list 
                        if genre_filter in track_to_genres.get(u, [])
                    ]
                else:
                    filtered_tracks = all_tracks_list
            
            if not filtered_tracks:
                log(f"    ⚠️  No {genre_filter or 'all'} tracks for {year}, skipping {playlist_name}")
                continue
            
            # Create or update playlist
            if playlist_name in existing:
                # If we're not consolidating from monthly playlists (they were already deleted),
                # and the playlist already exists, skip the expensive check
                if year not in monthly_playlists:
                    log(f"  {playlist_name}: already consolidated (skipping check)")
                    continue
                
                pid = existing[playlist_name]
                # Get existing tracks (includes both auto-added and manually added tracks)
                already = get_playlist_tracks(sp, pid)
                # Only add tracks that aren't already present (preserves manual additions)
                to_add = [u for u in filtered_tracks if u not in already]
                
                if to_add:
                    for chunk in _chunked(to_add, 50):
                        api_call(sp.playlist_add_items, pid, chunk)
                    log(f"  {playlist_name}: +{len(to_add)} tracks (total: {len(filtered_tracks)}; manually added tracks preserved)")
                else:
                    log(f"  {playlist_name}: already up to date ({len(filtered_tracks)} tracks)")
            else:
                # Calculate last date of the year for creation date reference
                # Note: Spotify API doesn't support setting creation date directly
                period_end = datetime(year, 12, 31, 23, 59, 59)
                
                # Check for duplicate before creating
                if playlist_name in existing:
                    log(f"  ⚠️  Playlist {playlist_name} already exists, skipping creation")
                    continue
                
                pl = api_call(
                    sp.user_playlist_create,
                    user_id,
                    playlist_name,
                    public=False,
                    description=format_playlist_description(description, period=str(year), playlist_type=playlist_type),
                )
                pid = pl["id"]
                
                for chunk in _chunked(filtered_tracks, 50):
                    api_call(sp.playlist_add_items, pid, chunk)
                log(f"  {playlist_name}: created with {len(filtered_tracks)} tracks")
        
            # Delete old monthly playlists if they existed
            if year in monthly_playlists and playlist_type in monthly_playlists[year]:
                for monthly_name, monthly_id in monthly_playlists[year][playlist_type]:
                    try:
                        api_call(sp.user_playlist_unfollow, user_id, monthly_id)
                        # Invalidate cache since we deleted a playlist
                        _invalidate_playlist_cache()
                        log(f"    ✓ Deleted {monthly_name}")
                    except Exception as e:
                        log(f"    ⚠️  Failed to delete {monthly_name}: {e}")
        
        log(f"  ✅ Consolidated {year} into yearly playlists for all types")


def delete_old_monthly_playlists(sp: spotipy.Spotify) -> None:
    """Delete old genre-split monthly playlists older than cutoff year.
    
    Standard monthly playlists are handled by consolidate_old_monthly_playlists().
    This function only handles genre-split playlists (HipHopFindsJan23, etc.).
    """
    log("\n--- Deleting Old Genre-Split Monthly Playlists ---")
    
    current_year = datetime.now().year
    cutoff_year = current_year  # Keep only the current year as monthly
    
    # Get all existing playlists
    existing = get_existing_playlists(sp)
    
    # Pattern for genre monthly: {genre}{prefix}{mon}{year}
    genre_patterns = []
    for genre in SPLIT_GENRES:
        genre_patterns.append(f"{genre}{PREFIX_GENRE_MONTHLY}")
    
    playlists_to_delete = []
    
    for playlist_name, playlist_id in existing.items():
        # Check genre-split monthly playlists only
        for genre_pattern in genre_patterns:
            if playlist_name.startswith(genre_pattern):
                for mon_abbr in MONTH_NAMES.values():
                    if playlist_name.startswith(f"{genre_pattern}{mon_abbr}"):
                        remaining = playlist_name[len(f"{genre_pattern}{mon_abbr}"):]
                        if remaining.isdigit():
                            year_str = remaining
                            # Convert 2-digit year to 4-digit (assume 2000s)
                            if len(year_str) == 2:
                                year = 2000 + int(year_str)
                            else:
                                year = int(year_str)
                            
                            if year < cutoff_year:
                                playlists_to_delete.append((playlist_name, playlist_id))
                        break
    
    if not playlists_to_delete:
        log("  No old genre-split monthly playlists to delete")
        return
    
    log(f"  Found {len(playlists_to_delete)} old genre-split monthly playlists to delete")
    
    # Get user ID for deletion (cached)
    user = get_user_info(sp)
    user_id = user["id"]
    
    for playlist_name, playlist_id in playlists_to_delete:
        try:
            api_call(sp.user_playlist_unfollow, user_id, playlist_id)
            # Invalidate cache since we deleted a playlist
            _invalidate_playlist_cache()
            log(f"    ✓ Deleted {playlist_name}")
        except Exception as e:
            log(f"    ⚠️  Failed to delete {playlist_name}: {e}")
    
    log(f"  ✅ Deleted {len(playlists_to_delete)} old genre-split monthly playlists")


def update_genre_split_playlists(sp: spotipy.Spotify, month_to_tracks: dict) -> None:
    """Update genre-split monthly playlists (HipHop, Dance, Other).
    
    Note: This function only ADDS tracks from liked songs. It never removes tracks.
    Manually added tracks are preserved and will remain in the playlists.
    """
    if not month_to_tracks:
        return
    
    log("\n--- Genre-Split Playlists ---")
    
    # Load genre data
    track_artists = pd.read_parquet(DATA_DIR / "track_artists.parquet")
    artists = pd.read_parquet(DATA_DIR / "artists.parquet")
    
    artist_genres_map = artists.set_index("artist_id")["genres"].to_dict()
    
    # Build track -> genres mapping (tracks can have multiple genres)
    # Try to use stored track genres first
    track_to_genres = {}
    tracks_df = pd.read_parquet(DATA_DIR / "tracks.parquet")
    if "genres" in tracks_df.columns:
        # Use stored track genres
        for _, track_row in tracks_df.iterrows():
            track_id = track_row["track_id"]
            uri = f"spotify:track:{track_id}"
            stored_genres = _parse_genres(track_row.get("genres"))
            if stored_genres:
                split_genres = get_all_split_genres(stored_genres)
                if split_genres:
                    track_to_genres[uri] = split_genres
    
    # Fill in missing using artist data
    all_uris = set(u for uris in month_to_tracks.values() for u in uris)
    track_ids = {u.split(":")[-1] for u in all_uris if u.startswith("spotify:track:")}
    
    for track_id in track_ids:
        uri = f"spotify:track:{track_id}"
        if uri in track_to_genres:
            continue  # Already have from stored data
        
        # Get all genres from all artists on this track
        all_track_genres = _get_all_track_genres(track_id, track_artists, artist_genres_map)
        split_genres = get_all_split_genres(all_track_genres)
        if split_genres:
            track_to_genres[uri] = split_genres
    
    # Get existing playlists (cached)
    existing = get_existing_playlists(sp)
    user = get_user_info(sp)
    user_id = user["id"]
    
    for month, uris in sorted(month_to_tracks.items()):
        for genre in SPLIT_GENRES:
            # Tracks can match multiple genres, check if this genre is in the list
            genre_uris = [u for u in uris if genre in track_to_genres.get(u, [])]
            
            if not genre_uris:
                continue
            
            name = format_playlist_name(GENRE_MONTHLY_TEMPLATE, month, genre, playlist_type="genre_monthly")
            
            if name in existing:
                pid = existing[name]
                # Get existing tracks (includes both auto-added and manually added tracks)
                already = get_playlist_tracks(sp, pid)
                # Only add tracks that aren't already present (preserves manual additions)
                to_add = [u for u in genre_uris if u not in already]

                if to_add:
                    for chunk in _chunked(to_add, 50):
                        api_call(sp.playlist_add_items, pid, chunk)
                    # Invalidate cache for this playlist since we added tracks
                    if pid in _playlist_tracks_cache:
                        del _playlist_tracks_cache[pid]
                    log(f"  {name}: +{len(to_add)} tracks (manually added tracks preserved)")
            else:
                pl = api_call(
                    sp.user_playlist_create,
                    user_id,
                    name,
                    public=False,
                    description=format_playlist_description(f"{genre} tracks", period=month, genre=genre, playlist_type="genre_monthly"),
                )
                pid = pl["id"]

                for chunk in _chunked(genre_uris, 50):
                    api_call(sp.playlist_add_items, pid, chunk)
                # Invalidate playlist cache since we created a new playlist
                _invalidate_playlist_cache()
                log(f"  {name}: created with {len(genre_uris)} tracks")


def update_master_genre_playlists(sp: spotipy.Spotify) -> None:
    """Update master genre playlists with all liked songs by genre.
    
    Note: This function only ADDS tracks from liked songs. It never removes tracks.
    Manually added tracks are preserved and will remain in the playlists.
    """
    log("\n--- Master Genre Playlists ---")
    
    # Load data
    library = pd.read_parquet(DATA_DIR / "playlist_tracks.parquet")
    track_artists = pd.read_parquet(DATA_DIR / "track_artists.parquet")
    artists = pd.read_parquet(DATA_DIR / "artists.parquet")
    
    # Get liked songs
    liked = library[library["playlist_id"].astype(str) == LIKED_SONGS_PLAYLIST_ID]
    liked_ids = set(liked["track_id"])
    
    # Build URIs
    if "track_uri" in liked.columns:
        liked_uris = liked["track_uri"].dropna().tolist()
    else:
        liked_uris = [f"spotify:track:{tid}" for tid in liked_ids]
    
    # Build genre mapping - tracks can have MULTIPLE broad genres
    # Try to use stored track genres first, then fall back to artist genres
    uri_to_genres = {}  # Map URI to list of broad genres
    tracks_df = pd.read_parquet(DATA_DIR / "tracks.parquet")
    
    if "genres" in tracks_df.columns:
        # Use stored track genres and convert to broad genres
        for _, track_row in tracks_df.iterrows():
            track_id = track_row["track_id"]
            if track_id not in liked_ids:
                continue
            uri = f"spotify:track:{track_id}"
            stored_genres = _parse_genres(track_row.get("genres"))
            if stored_genres:
                # Convert stored genres to broad genres
                broad_genres = get_all_broad_genres(stored_genres)
                if broad_genres:
                    uri_to_genres[uri] = broad_genres
    
    # Fill in missing using artist data
    artist_genres_map = artists.set_index("artist_id")["genres"].to_dict()
    for track_id in liked_ids:
        uri = f"spotify:track:{track_id}"
        if uri in uri_to_genres:
            continue  # Already have from stored data
        
        # Get all genres from all artists on this track
        all_track_genres = _get_all_track_genres(track_id, track_artists, artist_genres_map)
        # Get ALL matching broad genres (tracks can match multiple)
        broad_genres = get_all_broad_genres(all_track_genres)
        if broad_genres:
            uri_to_genres[uri] = broad_genres
    
    # Count tracks per genre (tracks can contribute to multiple genres)
    genre_counts = Counter()
    for genres_list in uri_to_genres.values():
        for genre in genres_list:
            genre_counts[genre] += 1
    
    # Select top genres
    selected = [g for g, n in genre_counts.most_common(MAX_GENRE_PLAYLISTS) 
                if n >= MIN_TRACKS_FOR_GENRE]
    
    log(f"  Found {len(selected)} genre(s) with >= {MIN_TRACKS_FOR_GENRE} tracks")
    
    # Get existing playlists (cached)
    existing = get_existing_playlists(sp)
    user = get_user_info(sp)
    user_id = user["id"]
    
    for genre in selected:
        # Get all tracks that match this genre (tracks can match multiple genres)
        uris = [u for u in liked_uris if genre in uri_to_genres.get(u, [])]
        if not uris:
            continue
        
        name = format_playlist_name(GENRE_NAME_TEMPLATE, genre=genre, playlist_type="genre_master")
        
        if name in existing:
            pid = existing[name]
            # Get existing tracks (includes both auto-added and manually added tracks)
            already = get_playlist_tracks(sp, pid)
            # Only add tracks that aren't already present (preserves manual additions)
            to_add = [u for u in uris if u not in already]

            if to_add:
                for chunk in _chunked(to_add, 50):
                    api_call(sp.playlist_add_items, pid, chunk)
                # Invalidate cache for this playlist since we added tracks
                if pid in _playlist_tracks_cache:
                    del _playlist_tracks_cache[pid]
                log(f"  {name}: +{len(to_add)} tracks (manually added tracks preserved)")
        else:
            pl = api_call(
                sp.user_playlist_create,
                user_id,
                name,
                public=False,
                description=format_playlist_description("All liked songs", genre=genre, playlist_type="genre_master"),
            )
            pid = pl["id"]

            for chunk in _chunked(uris, 50):
                api_call(sp.playlist_add_items, pid, chunk)
            # Invalidate playlist cache since we created a new playlist
            _invalidate_playlist_cache()
            log(f"  {name}: created with {len(uris)} tracks")


# ============================================================================
# DUPLICATE PLAYLIST DETECTION & DELETION
# ============================================================================

def delete_duplicate_playlists(sp: spotipy.Spotify) -> None:
    """Delete duplicate playlists based on track content (same tracks, different names).
    
    Compares all playlists and identifies duplicates by checking if they have
    the same set of tracks. Keeps the first playlist (by name) and deletes others.
    """
    log("\n--- Detecting and Deleting Duplicate Playlists ---")
    
    existing = get_existing_playlists(sp, force_refresh=True)
    user = get_user_info(sp)
    user_id = user["id"]
    
    if not existing:
        log("  ℹ️  No playlists found")
        return
    
    log(f"  Checking {len(existing)} playlist(s) for duplicates...")
    
    # Limit duplicate checking to reasonable number of playlists to avoid timeout
    # Focus on playlists that might be duplicates (similar names or automated playlists)
    # Allow override via environment variable
    max_playlists = int(os.environ.get("MAX_PLAYLISTS_FOR_DUPLICATE_CHECK", "1000"))
    if len(existing) > max_playlists:
        log(f"  ⚠️  Too many playlists ({len(existing):,}) - skipping duplicate detection")
        log(f"      Set MAX_PLAYLISTS_FOR_DUPLICATE_CHECK env var to override (current limit: {max_playlists})")
        return
    
    # Build track set for each playlist
    playlist_track_sets = {}
    checked = 0
    for name, playlist_id in existing.items():
        try:
            tracks = get_playlist_tracks(sp, playlist_id, force_refresh=False)  # Use cache if available
            # Convert to frozenset for comparison (order doesn't matter)
            track_set = frozenset(tracks)
            if track_set in playlist_track_sets:
                # Found a duplicate - add to the list
                playlist_track_sets[track_set].append((name, playlist_id))
            else:
                playlist_track_sets[track_set] = [(name, playlist_id)]
            checked += 1
            if checked % 50 == 0:
                log(f"  Progress: checked {checked}/{len(existing)} playlists...")
        except Exception as e:
            log(f"  ⚠️  Could not read tracks from '{name}': {e}")
            continue
    
    # Find duplicates (playlists with same track set)
    deleted_count = 0
    for track_set, playlists in playlist_track_sets.items():
        if len(playlists) > 1 and len(track_set) > 0:  # Only consider non-empty playlists
            # Sort by name to keep the first one (alphabetically)
            playlists_sorted = sorted(playlists, key=lambda x: x[0])
            keep_playlist = playlists_sorted[0]
            duplicates = playlists_sorted[1:]
            
            log(f"  🔍 Found {len(playlists)} duplicate playlist(s) with {len(track_set)} tracks:")
            log(f"     ✅ Keeping: '{keep_playlist[0]}'")
            
            for dup_name, dup_id in duplicates:
                try:
                    api_call(sp.user_playlist_unfollow, user_id, dup_id)
                    log(f"     🗑️  Deleted: '{dup_name}'")
                    deleted_count += 1
                    # Remove from cache
                    _invalidate_playlist_cache()
                    if dup_name in existing:
                        del existing[dup_name]
                except Exception as e:
                    log(f"     ⚠️  Failed to delete '{dup_name}': {e}")
    
    if deleted_count > 0:
        log(f"  ✅ Deleted {deleted_count} duplicate playlist(s)")
    else:
        log("  ℹ️  No duplicate playlists found")


# ============================================================================
# MAIN
# ============================================================================

def main():
    # Load environment variables from .env file if available
    if DOTENV_AVAILABLE:
        env_path = PROJECT_ROOT / ".env"
        if env_path.exists():
            load_dotenv(env_path)
    
    # Clear log buffer at start
    global _log_buffer
    _log_buffer = []
    
    parser = argparse.ArgumentParser(
        description="Sync Spotify library and update playlists",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/spotify_sync.py              # Full sync + update
    python scripts/spotify_sync.py --skip-sync  # Update only (fast)
    python scripts/spotify_sync.py --sync-only  # Sync only, no playlist changes
    python scripts/spotify_sync.py --all-months # Process all months
        """
    )
    parser.add_argument(
        "--skip-sync", action="store_true",
        help="Skip data sync, use existing parquet files (faster for local runs)"
    )
    parser.add_argument(
        "--sync-only", action="store_true",
        help="Only sync data, don't update playlists"
    )
    parser.add_argument(
        "--all-months", action="store_true",
        help="Process all months (deprecated: now uses last 3 months by default)"
    )
    args = parser.parse_args()
    
    log("=" * 60)
    log("Spotify Sync & Playlist Update")
    log("=" * 60)
    
    success = False
    error = None
    summary = {}
    
    # Authenticate
    try:
        sp = get_spotify_client()
        user = get_user_info(sp)
        log(f"Authenticated as: {user['display_name']} ({user['id']})")
    except Exception as e:
        log(f"ERROR: Authentication failed: {e}")
        error = e
        _send_email_notification(False, error=error)
        sys.exit(1)
    
    try:
        # Data sync phase
        if not args.skip_sync:
            with timed_step("Full Library Sync"):
                # Full library sync using spotim8 (includes liked songs and artists)
                sync_success = sync_full_library()
                summary["sync_completed"] = "Yes" if sync_success else "No"
        
        # Playlist update phase
        if not args.sync_only:
            with timed_step("Rename Playlists with Old Prefixes"):
                # Rename playlists with old prefixes (runs first, before other updates)
                rename_playlists_with_old_prefixes(sp)
            
            with timed_step("Fix Incorrectly Named Yearly Genre Playlists"):
                # Fix yearly genre playlists that were created with wrong template
                fix_incorrectly_named_yearly_genre_playlists(sp)
            
            with timed_step("Consolidate Old Monthly Playlists"):
                # Consolidate old monthly playlists into yearly (runs first)
                # Consolidates anything older than the last N months (default: 3)
                consolidate_old_monthly_playlists(sp, keep_last_n_months=KEEP_MONTHLY_MONTHS)
            
            with timed_step("Delete Old Monthly Playlists"):
                # Delete old monthly playlists (including genre-split)
                delete_old_monthly_playlists(sp)
            
            with timed_step("Update Monthly Playlists"):
                # Update monthly playlists (only last N months, default: 3)
                month_to_tracks = update_monthly_playlists(
                    sp, keep_last_n_months=KEEP_MONTHLY_MONTHS
                )
                if month_to_tracks:
                    summary["months_processed"] = len(month_to_tracks)
            
            # Update genre-split playlists
            if month_to_tracks:
                with timed_step("Update Genre-Split Playlists"):
                    update_genre_split_playlists(sp, month_to_tracks)
            
            with timed_step("Update Master Genre Playlists"):
                # Update master genre playlists
                update_master_genre_playlists(sp)
        
        log("\n" + "=" * 60)
        log("✅ Complete!")
        log("=" * 60)
        success = True
        
    except Exception as e:
        log(f"ERROR: {e}")
        import traceback
        error_trace = traceback.format_exc()
        log(error_trace)
        error = e
        success = False
    
    finally:
        # Send email notification
        _send_email_notification(success, summary=summary, error=error)
        
        if not success:
            sys.exit(1)


def _send_email_notification(success: bool, summary: dict = None, error: Exception = None):
    """Helper to send email notification with captured logs."""
    if not EMAIL_AVAILABLE:
        log("  ℹ️  Email notifications not available (email_notify.py not found)")
        return
    
    if not is_email_enabled():
        log("  ℹ️  Email notifications disabled (EMAIL_ENABLED not set to true)")
        return
    
    log_output = "\n".join(_log_buffer)
    
    try:
        log("  📧 Sending email notification...")
        email_sent = send_email_notification(
            success=success,
            log_output=log_output,
            summary=summary or {},
            error=error
        )
        if email_sent:
            log("  ✅ Email notification sent successfully")
        else:
            log("  ⚠️  Email notification failed (check email configuration)")
    except Exception as e:
        # Don't fail the sync if email fails
        log(f"  ⚠️  Email notification error (non-fatal): {e}")
        import traceback
        log(traceback.format_exc())


if __name__ == "__main__":
    main()

