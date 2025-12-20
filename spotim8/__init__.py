"""
Spotim8 - Pandas-first interface to Spotify Web API.

Turns Spotify into tidy DataFrames you can merge().

Usage:
    from spotim8 import Spotim8
    
    sf = Spotim8.from_env(progress=True)
    sf.sync()
    
    playlists = sf.playlists()
    tracks = sf.tracks()
    artists = sf.artists()
"""

from .client import (
    Spotim8,
    LIKED_SONGS_PLAYLIST_ID,
    LIKED_SONGS_PLAYLIST_NAME,
    DEFAULT_SCOPE,
)
from .catalog import CacheConfig, DataCatalog
from .export import export_table
from .features import (
    playlist_profile_features,
    artist_concentration_features,
    time_features,
    release_year_features,
    popularity_tier_features,
    build_all_features,
)

__version__ = "0.2.0"

__all__ = [
    # Main client
    "Spotim8",
    # Constants
    "LIKED_SONGS_PLAYLIST_ID",
    "LIKED_SONGS_PLAYLIST_NAME",
    "DEFAULT_SCOPE",
    # Configuration
    "CacheConfig",
    "DataCatalog",
    # Utilities
    "export_table",
    # Feature engineering
    "playlist_profile_features",
    "artist_concentration_features",
    "time_features",
    "release_year_features",
    "popularity_tier_features",
    "build_all_features",
]
