"""
Configuration module for sync automation.

All environment variables and configuration constants are defined here.
"""

import os
from pathlib import Path

# Try to load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False


def _parse_bool_env(key: str, default: bool = True) -> bool:
    """Parse boolean environment variable."""
    value = os.environ.get(key, str(default)).lower()
    return value in ("true", "1", "yes", "on")


# Get project root (assumes this file is at spotim8/scripts/automation/config.py)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

# Load .env file early so environment variables are available
if DOTENV_AVAILABLE:
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path)

# ============================================================================
# BASIC CONFIGURATION
# ============================================================================
# Most commonly customized settings - users typically only change these
OWNER_NAME = os.environ.get("PLAYLIST_OWNER_NAME", "AJ")
BASE_PREFIX = os.environ.get("PLAYLIST_PREFIX", "Finds")

# Playlist type enable/disable flags
# Set to "false" in .env to disable specific playlist types
ENABLE_MONTHLY = _parse_bool_env("PLAYLIST_ENABLE_MONTHLY", True)
ENABLE_MOST_PLAYED = _parse_bool_env("PLAYLIST_ENABLE_MOST_PLAYED", True)
ENABLE_DISCOVERY = _parse_bool_env("PLAYLIST_ENABLE_DISCOVERY", True)

# Individual prefixes for different playlist types
# Most users don't need to customize these - defaults work well
# Only set if you want different prefixes for different playlist types
PREFIX_MONTHLY = os.environ.get("PLAYLIST_PREFIX_MONTHLY", BASE_PREFIX)
PREFIX_GENRE_MONTHLY = os.environ.get("PLAYLIST_PREFIX_GENRE_MONTHLY", BASE_PREFIX)
PREFIX_YEARLY = os.environ.get("PLAYLIST_PREFIX_YEARLY", BASE_PREFIX)
PREFIX_GENRE_MASTER = os.environ.get("PLAYLIST_PREFIX_GENRE_MASTER", "am")
PREFIX_MOST_PLAYED = os.environ.get("PLAYLIST_PREFIX_MOST_PLAYED", "Top")
PREFIX_TIME_BASED = os.environ.get("PLAYLIST_PREFIX_TIME_BASED", "Vibes")  # Deprecated: feature removed
PREFIX_REPEAT = os.environ.get("PLAYLIST_PREFIX_REPEAT", "OnRepeat")  # Deprecated: feature removed
PREFIX_DISCOVERY = os.environ.get("PLAYLIST_PREFIX_DISCOVERY", "Discovery")

# ============================================================================
# PLAYLIST NAME TEMPLATES
# ============================================================================
# Advanced customization - rarely changed, good defaults provided
# Only customize if you need non-standard playlist naming

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
    "{owner}{prefix}{mon}{year}"
)
REPEAT_TEMPLATE = os.environ.get(
    "PLAYLIST_TEMPLATE_REPEAT",
    "{owner}{prefix}{mon}{year}"
)
DISCOVERY_TEMPLATE = os.environ.get(
    "PLAYLIST_TEMPLATE_DISCOVERY",
    "{owner}{prefix}{mon}{year}"
)

# ============================================================================
# PLAYLIST LIMITS AND RETENTION
# ============================================================================

MIN_TRACKS_FOR_GENRE = 20
MAX_GENRE_PLAYLISTS = 19
KEEP_MONTHLY_MONTHS = int(os.environ.get("KEEP_MONTHLY_MONTHS", "3"))

# ============================================================================
# FORMATTING OPTIONS
# ============================================================================
# Advanced formatting customization - most users don't need to change these
DATE_FORMAT = os.environ.get("PLAYLIST_DATE_FORMAT", "short")  # Options: short, medium, long, numeric
SEPARATOR_MONTH = os.environ.get("PLAYLIST_SEPARATOR_MONTH", "none")  # Options: none, space, dash, underscore
SEPARATOR_PREFIX = os.environ.get("PLAYLIST_SEPARATOR_PREFIX", "none")  # Options: none, space, dash, underscore
CAPITALIZATION = os.environ.get("PLAYLIST_CAPITALIZATION", "preserve")  # Options: title, upper, lower, preserve
DESCRIPTION_TEMPLATE = os.environ.get(
    "PLAYLIST_DESCRIPTION_TEMPLATE",
    "{description} from {period} (automatically updated; manual additions welcome)"
)

# ============================================================================
# PATHS AND CONSTANTS
# ============================================================================

DATA_DIR = PROJECT_ROOT / "data"
LIKED_SONGS_PLAYLIST_ID = "__liked_songs__"  # Match spotim8 library constant

# ============================================================================
# MONTH NAME MAPPINGS
# ============================================================================

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

