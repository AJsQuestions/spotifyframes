"""
Feature engineering utilities for playlist analysis.

Note: Spotify deprecated audio features in November 2024.
This module focuses on features that are still available:
- Popularity metrics
- Artist concentration
- Temporal patterns
- Genre-based features
"""

from __future__ import annotations

import warnings
from typing import Optional

import numpy as np
import pandas as pd


# Deprecated - kept for backwards compatibility reference
AUDIO_COLS = [
    "danceability", "energy", "valence", "tempo", "loudness",
    "acousticness", "instrumentalness", "liveness", "speechiness"
]


def playlist_profile_features(
    wide: pd.DataFrame,
    playlist_col: str = "playlist_id"
) -> pd.DataFrame:
    """
    Aggregate popularity and available metrics per playlist.
    
    Note: Audio features (danceability, energy, etc.) are no longer available
    from Spotify's API as of November 2024.
    
    Args:
        wide: Wide table from SpotifyFrames.library_wide()
        playlist_col: Column name for playlist ID
        
    Returns:
        DataFrame with aggregated features per playlist
    """
    df = wide.copy()
    
    agg = {}
    
    # Popularity is still available
    if "popularity" in df.columns:
        agg["popularity"] = ["mean", "std", "median", "min", "max"]
    
    # Duration is still available
    if "duration_ms" in df.columns:
        agg["duration_ms"] = ["mean", "std", "median", "min", "max"]
    
    # Check for any remaining audio columns (legacy data)
    available_audio = [c for c in AUDIO_COLS if c in df.columns]
    if available_audio:
        warnings.warn(
            f"Found legacy audio columns: {available_audio}. "
            "Note: Spotify deprecated audio features in Nov 2024.",
            DeprecationWarning,
            stacklevel=2
        )
        for c in available_audio:
            agg[c] = ["mean", "std", "median"]
    
    if not agg:
        return pd.DataFrame({playlist_col: df[playlist_col].unique()})
    
    g = df.groupby(playlist_col).agg(agg)
    g.columns = ["_".join([a, b]) for a, b in g.columns]
    return g.reset_index()


def artist_concentration_features(
    wide: pd.DataFrame,
    playlist_col: str = "playlist_id",
    artist_col: str = "primary_artist_id"
) -> pd.DataFrame:
    """
    Calculate artist concentration metrics per playlist.
    
    Returns HHI (Herfindahl-Hirschman Index) and entropy of artist distribution.
    Higher HHI = more concentrated (fewer artists dominate).
    Higher entropy = more diverse (many artists equally represented).
    
    Args:
        wide: Wide table from SpotifyFrames.library_wide()
        playlist_col: Column name for playlist ID
        artist_col: Column name for primary artist ID
        
    Returns:
        DataFrame with artist_hhi and artist_entropy per playlist
    """
    df = wide.dropna(subset=[playlist_col, artist_col]).copy()
    
    if len(df) == 0:
        return pd.DataFrame(columns=[playlist_col, "artist_hhi", "artist_entropy"])
    
    counts = df.groupby([playlist_col, artist_col])["track_id"].nunique().reset_index(name="n")
    totals = counts.groupby(playlist_col)["n"].sum().rename("N").reset_index()
    m = counts.merge(totals, on=playlist_col, how="left")
    m["p"] = m["n"] / m["N"]
    
    # HHI: sum of squared market shares
    hhi = m.groupby(playlist_col)["p"].apply(lambda x: float((x ** 2).sum())).rename("artist_hhi")
    
    # Entropy: -sum(p * log(p))
    ent = m.groupby(playlist_col)["p"].apply(
        lambda x: float(-(x * np.log(x + 1e-12)).sum())
    ).rename("artist_entropy")
    
    return pd.concat([hhi, ent], axis=1).reset_index()


def time_features(
    wide: pd.DataFrame,
    added_at_col: str = "added_at",
    playlist_col: str = "playlist_id"
) -> pd.DataFrame:
    """
    Calculate temporal features based on when tracks were added.
    
    Args:
        wide: Wide table from SpotifyFrames.library_wide()
        added_at_col: Column name for added timestamp
        playlist_col: Column name for playlist ID
        
    Returns:
        DataFrame with age statistics per playlist
    """
    if added_at_col not in wide.columns:
        return pd.DataFrame({playlist_col: wide[playlist_col].dropna().unique()})
    
    df = wide.copy()
    df[added_at_col] = pd.to_datetime(df[added_at_col], errors="coerce", utc=True)
    now = pd.Timestamp.utcnow()
    df["age_days"] = (now - df[added_at_col]).dt.total_seconds() / 86400.0
    
    g = df.groupby(playlist_col)["age_days"].agg(["mean", "median", "min", "max"]).reset_index()
    g = g.rename(columns={c: f"added_age_days_{c}" for c in ["mean", "median", "min", "max"]})
    return g


def release_year_features(
    wide: pd.DataFrame,
    release_date_col: str = "release_date",
    playlist_col: str = "playlist_id"
) -> pd.DataFrame:
    """
    Calculate release year statistics per playlist.
    
    Args:
        wide: Wide table from SpotifyFrames.library_wide()
        release_date_col: Column name for release date
        playlist_col: Column name for playlist ID
        
    Returns:
        DataFrame with release year statistics per playlist
    """
    if release_date_col not in wide.columns:
        return pd.DataFrame({playlist_col: wide[playlist_col].dropna().unique()})
    
    df = wide.copy()
    
    # Extract year from release date (handles YYYY, YYYY-MM, YYYY-MM-DD formats)
    def extract_year(x):
        if pd.isna(x):
            return np.nan
        try:
            return int(str(x)[:4])
        except:
            return np.nan
    
    df["release_year"] = df[release_date_col].apply(extract_year)
    
    g = df.groupby(playlist_col)["release_year"].agg(["mean", "median", "min", "max", "std"]).reset_index()
    g = g.rename(columns={c: f"release_year_{c}" for c in ["mean", "median", "min", "max", "std"]})
    return g


def popularity_tier_features(
    wide: pd.DataFrame,
    popularity_col: str = "popularity",
    playlist_col: str = "playlist_id"
) -> pd.DataFrame:
    """
    Calculate popularity tier distribution per playlist.
    
    Tiers:
    - underground: 0-20
    - niche: 21-40  
    - moderate: 41-60
    - popular: 61-80
    - mainstream: 81-100
    
    Args:
        wide: Wide table from SpotifyFrames.library_wide()
        popularity_col: Column name for popularity score
        playlist_col: Column name for playlist ID
        
    Returns:
        DataFrame with tier percentages per playlist
    """
    if popularity_col not in wide.columns:
        return pd.DataFrame({playlist_col: wide[playlist_col].dropna().unique()})
    
    df = wide.copy()
    
    def tier(p):
        if pd.isna(p):
            return "unknown"
        if p <= 20:
            return "underground"
        if p <= 40:
            return "niche"
        if p <= 60:
            return "moderate"
        if p <= 80:
            return "popular"
        return "mainstream"
    
    df["tier"] = df[popularity_col].apply(tier)
    
    # Calculate tier percentages
    tier_counts = df.groupby([playlist_col, "tier"])["track_id"].count().unstack(fill_value=0)
    tier_pcts = tier_counts.div(tier_counts.sum(axis=1), axis=0)
    tier_pcts.columns = [f"pct_{c}" for c in tier_pcts.columns]
    
    return tier_pcts.reset_index()


def build_all_features(
    wide: pd.DataFrame,
    playlist_col: str = "playlist_id"
) -> pd.DataFrame:
    """
    Build all available features for playlists.
    
    Combines:
    - Profile features (popularity, duration stats)
    - Artist concentration (HHI, entropy)
    - Time features (track age)
    - Release year features
    - Popularity tier features
    
    Args:
        wide: Wide table from SpotifyFrames.library_wide()
        playlist_col: Column name for playlist ID
        
    Returns:
        DataFrame with all features per playlist
    """
    features = [
        playlist_profile_features(wide, playlist_col),
        artist_concentration_features(wide, playlist_col),
        time_features(wide, playlist_col=playlist_col),
        release_year_features(wide, playlist_col=playlist_col),
        popularity_tier_features(wide, playlist_col=playlist_col),
    ]
    
    result = features[0]
    for f in features[1:]:
        result = result.merge(f, on=playlist_col, how="outer")
    
    return result
