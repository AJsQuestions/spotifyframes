"""
Helper functions for creating playlists with proper dates and duplicate prevention.
"""

from datetime import datetime
from calendar import monthrange
from typing import Optional


def get_period_end_date(period_type: str, period_value: str) -> Optional[datetime]:
    """
    Get the last date/time of a period for setting playlist creation dates.
    
    Args:
        period_type: "month" or "year"
        period_value: "YYYY-MM" for month, "YYYY" for year
    
    Returns:
        datetime object representing the end of the period, or None if invalid
    """
    try:
        if period_type == "month":
            year, month = map(int, period_value.split("-"))
            last_day = monthrange(year, month)[1]
            return datetime(year, month, last_day, 23, 59, 59)
        elif period_type == "year":
            year = int(period_value)
            return datetime(year, 12, 31, 23, 59, 59)
    except (ValueError, AttributeError):
        return None
    return None


def check_duplicate_playlist(existing_playlists: dict, playlist_name: str) -> bool:
    """
    Check if a playlist with the same name already exists.
    
    Args:
        existing_playlists: Dictionary of {name: playlist_id}
        playlist_name: Name to check
    
    Returns:
        True if duplicate exists, False otherwise
    """
    return playlist_name in existing_playlists

