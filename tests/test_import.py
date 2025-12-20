"""Test that all public exports are importable."""

import pytest


def test_import_main():
    """Test importing main module."""
    import spotim8
    assert hasattr(spotim8, 'Spotim8')
    assert hasattr(spotim8, '__version__')


def test_import_client():
    """Test importing from client."""
    from spotim8 import Spotim8, LIKED_SONGS_PLAYLIST_ID, LIKED_SONGS_PLAYLIST_NAME
    assert Spotim8 is not None
    assert LIKED_SONGS_PLAYLIST_ID == "__liked_songs__"


def test_import_catalog():
    """Test importing catalog classes."""
    from spotim8 import CacheConfig, DataCatalog
    assert CacheConfig is not None
    assert DataCatalog is not None


def test_import_features():
    """Test importing feature functions."""
    from spotim8 import (
        playlist_profile_features,
        artist_concentration_features,
        time_features,
        release_year_features,
        popularity_tier_features,
        build_all_features,
    )
    assert all([
        playlist_profile_features,
        artist_concentration_features,
        time_features,
        release_year_features,
        popularity_tier_features,
        build_all_features,
    ])


def test_import_ratelimit():
    """Test importing rate limiting utilities."""
    from spotim8.ratelimit import (
        rate_limited_call,
        RateLimiter,
        RateLimitError,
        DEFAULT_REQUEST_DELAY,
    )
    assert rate_limited_call is not None
    assert RateLimiter is not None
    assert RateLimitError is not None
    assert DEFAULT_REQUEST_DELAY > 0


def test_import_market():
    """Test importing market module."""
    from spotim8.market import MarketFrames
    assert MarketFrames is not None
