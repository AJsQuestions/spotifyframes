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

from .core.client import (
    Spotim8,
    LIKED_SONGS_PLAYLIST_ID,
    LIKED_SONGS_PLAYLIST_NAME,
    DEFAULT_SCOPE,
)
from .core.catalog import CacheConfig, DataCatalog
from .utils.ratelimit import set_response_cache
from .data.export import export_table
from .features.features import (
    playlist_profile_features,
    artist_concentration_features,
    time_features,
    release_year_features,
    popularity_tier_features,
    build_all_features,
)
from .features.genres import (
    GENRE_SPLIT_RULES,
    SPLIT_GENRES,
    GENRE_RULES,
    ALL_BROAD_GENRES,
    get_split_genre,
    get_broad_genre,
    get_all_split_genres,
    get_all_broad_genres,
)
from .analysis.analysis import (
    LibraryAnalyzer,
    PlaylistSimilarityEngine,
    get_genres_list,
    build_playlist_genre_profiles,
    canonical_core_genre,
)
from .analysis.streaming_history import (
    sync_all_export_data,
    sync_streaming_history,
    load_streaming_history,
    load_search_queries_cached,
    load_wrapped_data_cached,
    load_follow_data_cached,
    load_library_snapshot_cached,
    load_playback_errors_cached,
    load_playback_retries_cached,
    load_webapi_events_cached,
)

__version__ = "3.0.0"

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
    "set_response_cache",
    # Utilities
    "export_table",
    # Feature engineering
    "playlist_profile_features",
    "artist_concentration_features",
    "time_features",
    "release_year_features",
    "popularity_tier_features",
    "build_all_features",
    # Genre classification
    "GENRE_SPLIT_RULES",
    "SPLIT_GENRES",
    "GENRE_RULES",
    "ALL_BROAD_GENRES",
    "get_split_genre",
    "get_broad_genre",
    "get_all_split_genres",
    "get_all_broad_genres",
    # Analysis utilities
    "LibraryAnalyzer",
    "PlaylistSimilarityEngine",
    "get_genres_list",
    "build_playlist_genre_profiles",
    "canonical_core_genre",
    # Streaming history and export data
    "sync_all_export_data",
    "sync_streaming_history",
    "load_streaming_history",
    "load_search_queries_cached",
    "load_wrapped_data_cached",
    "load_follow_data_cached",
    "load_library_snapshot_cached",
    "load_playback_errors_cached",
    "load_playback_retries_cached",
    "load_webapi_events_cached",
]
