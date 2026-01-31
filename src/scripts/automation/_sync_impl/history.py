"""
Streaming history helpers: most played, time-based, repeat, discovery.

Functions to derive track lists from streaming history DataFrames.
"""

import pandas as pd

from .settings import DEFAULT_DISCOVERY_TRACK_LIMIT


def get_most_played_tracks(
    history_df: pd.DataFrame, month_str: str = None, limit: int = 50
) -> list:
    """Get most played tracks for a given month (or all data if month_str is None)."""
    if history_df is None or history_df.empty:
        return []

    if month_str:
        month_data = history_df.copy()
        month_data["month"] = month_data["timestamp"].dt.to_period("M").astype(str)
        month_data = month_data[month_data["month"] == month_str].copy()
    else:
        month_data = history_df.copy()

    if month_data.empty:
        return []

    if "track_uri" in month_data.columns:
        track_col = "track_uri"
    elif "spotify_track_uri" in month_data.columns:
        track_col = "spotify_track_uri"
    else:
        return []

    track_stats = (
        month_data.groupby(track_col)
        .agg({"ms_played": ["count", "sum"]})
        .reset_index()
    )
    track_stats.columns = ["track_uri", "play_count", "total_ms"]
    track_stats = track_stats.sort_values(
        ["play_count", "total_ms"], ascending=False
    )
    top_tracks = track_stats.head(limit)["track_uri"].tolist()
    return [uri for uri in top_tracks if pd.notna(uri) and uri]


def get_time_based_tracks(
    history_df: pd.DataFrame,
    month_str: str = None,
    time_type: str = "morning",
    limit: int = 50,
) -> list:
    """Get tracks played at specific times (morning, afternoon, evening, night, weekend)."""
    if history_df is None or history_df.empty:
        return []

    if month_str:
        h = history_df.copy()
        h["month"] = h["timestamp"].dt.to_period("M").astype(str)
        month_data = h[h["month"] == month_str].copy()
    else:
        month_data = history_df.copy()

    if month_data.empty:
        return []

    if time_type == "morning":
        filtered = month_data[
            (month_data["hour"] >= 6) & (month_data["hour"] < 12)
        ]
    elif time_type == "afternoon":
        filtered = month_data[
            (month_data["hour"] >= 12) & (month_data["hour"] < 18)
        ]
    elif time_type == "evening":
        filtered = month_data[
            (month_data["hour"] >= 18) & (month_data["hour"] < 24)
        ]
    elif time_type == "night":
        filtered = month_data[
            (month_data["hour"] >= 0) & (month_data["hour"] < 6)
        ]
    elif time_type == "weekend":
        filtered = month_data[
            month_data["day_of_week_num"].isin([5, 6])
        ]
    else:
        return []

    if filtered.empty:
        return []

    if "track_uri" in filtered.columns:
        track_col = "track_uri"
    elif "spotify_track_uri" in filtered.columns:
        track_col = "spotify_track_uri"
    else:
        return []

    track_stats = (
        filtered.groupby(track_col)
        .agg({"ms_played": ["count", "sum"]})
        .reset_index()
    )
    track_stats.columns = ["track_uri", "play_count", "total_ms"]
    track_stats = track_stats.sort_values(
        ["play_count", "total_ms"], ascending=False
    )
    top_tracks = track_stats.head(limit)["track_uri"].tolist()
    return [uri for uri in top_tracks if pd.notna(uri) and uri]


def get_repeat_tracks(
    history_df: pd.DataFrame,
    month_str: str = None,
    min_repeats: int = 3,
    limit: int = 50,
) -> list:
    """Get tracks played multiple times (on repeat) in a given month."""
    if history_df is None or history_df.empty:
        return []

    if month_str:
        h = history_df.copy()
        h["month"] = h["timestamp"].dt.to_period("M").astype(str)
        month_data = h[h["month"] == month_str].copy()
    else:
        month_data = history_df.copy()

    if month_data.empty:
        return []

    if "track_uri" in month_data.columns:
        track_col = "track_uri"
    elif "spotify_track_uri" in month_data.columns:
        track_col = "spotify_track_uri"
    else:
        return []

    play_counts = (
        month_data.groupby(track_col).size().reset_index(name="play_count")
    )
    repeat_tracks = play_counts[play_counts["play_count"] >= min_repeats].copy()
    repeat_tracks = repeat_tracks.sort_values("play_count", ascending=False)
    top_tracks = repeat_tracks.head(limit)[track_col].tolist()
    return [uri for uri in top_tracks if pd.notna(uri) and uri]


def get_discovery_tracks(
    history_df: pd.DataFrame,
    month_str: str = None,
    limit: int = DEFAULT_DISCOVERY_TRACK_LIMIT,
) -> list:
    """Get newly discovered tracks (first time played) in a given month."""
    if history_df is None or history_df.empty:
        return []

    if "track_uri" in history_df.columns:
        track_col = "track_uri"
    elif "spotify_track_uri" in history_df.columns:
        track_col = "spotify_track_uri"
    else:
        return []

    if month_str:
        h = history_df.copy()
        h["month"] = h["timestamp"].dt.to_period("M").astype(str)
        month_data = h[h["month"] == month_str].copy()

        if month_data.empty:
            return []

        before_month = h[h["month"] < month_str]
        known_tracks = set()
        if not before_month.empty and track_col in before_month.columns:
            known_tracks = set(before_month[track_col].dropna().unique())

        month_tracks = month_data[track_col].dropna().unique()
        new_tracks = [uri for uri in month_tracks if uri not in known_tracks]

        first_plays = month_data[
            month_data[track_col].isin(new_tracks)
        ].sort_values("timestamp")
        first_plays = first_plays.drop_duplicates(
            subset=[track_col], keep="first"
        )
        sorted_new_tracks = first_plays[track_col].tolist()
        return sorted_new_tracks[:limit]
    else:
        first_plays = (
            history_df.sort_values("timestamp")
            .drop_duplicates(subset=[track_col], keep="first")
        )
        sorted_new_tracks = first_plays[track_col].tolist()
        return sorted_new_tracks[:limit]
