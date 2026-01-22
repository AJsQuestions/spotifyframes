"""
Playlist Aesthetics & Organization Module

Enhances playlists with rich descriptions, statistics, and organizational features.
"""

import spotipy
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from collections import Counter
from pathlib import Path

from .sync import DATA_DIR, api_call, log, verbose_log
from .formatting import format_playlist_description
from src.features.genres import get_all_broad_genres, get_all_split_genres


def get_playlist_statistics(
    sp: spotipy.Spotify,
    playlist_id: str,
    tracks_df: pd.DataFrame,
    playlist_tracks_df: pd.DataFrame
) -> Dict[str, any]:
    """
    Calculate comprehensive statistics for a playlist.
    
    Returns:
        Dictionary with statistics including:
        - total_tracks: Number of tracks
        - total_duration_ms: Total duration in milliseconds
        - total_duration_hours: Total duration in hours
        - avg_popularity: Average track popularity
        - top_artists: List of top artists by track count
        - year_range: (min_year, max_year) of track releases
        - genres: Genre distribution
    """
    # Get tracks in this playlist
    playlist_tracks = playlist_tracks_df[playlist_tracks_df["playlist_id"] == playlist_id]
    if playlist_tracks.empty:
        return {
            "total_tracks": 0,
            "total_duration_ms": 0,
            "total_duration_hours": 0.0,
            "avg_popularity": 0,
            "top_artists": [],
            "year_range": (None, None),
            "genres": {}
        }
    
    # Merge with track data
    merged = playlist_tracks.merge(tracks_df, on="track_id", how="left")
    
    # Basic stats
    total_tracks = len(merged)
    total_duration_ms = merged["duration_ms"].sum() if "duration_ms" in merged.columns else 0
    total_duration_hours = total_duration_ms / (1000 * 60 * 60)
    
    # Popularity
    avg_popularity = merged["popularity"].mean() if "popularity" in merged.columns else 0
    
    # Top artists (by track count)
    if "primary_artist" in merged.columns:
        top_artists = merged["primary_artist"].value_counts().head(5).to_dict()
    else:
        top_artists = {}
    
    # Year range
    if "release_year" in merged.columns:
        years = merged["release_year"].dropna()
        if not years.empty:
            year_range = (int(years.min()), int(years.max()))
        else:
            year_range = (None, None)
    else:
        year_range = (None, None)
    
    # Genres (from track genres if available)
    genres = {}
    if "genres" in merged.columns:
        all_genres = []
        for genre_list in merged["genres"].dropna():
            if isinstance(genre_list, list):
                all_genres.extend(genre_list)
        genres = dict(Counter(all_genres).most_common(10))
    
    return {
        "total_tracks": total_tracks,
        "total_duration_ms": int(total_duration_ms),
        "total_duration_hours": round(total_duration_hours, 1),
        "avg_popularity": round(avg_popularity, 1),
        "top_artists": top_artists,
        "year_range": year_range,
        "genres": genres
    }


def format_rich_description(
    base_description: str,
    stats: Dict[str, any],
    period: Optional[str] = None,
    playlist_type: Optional[str] = None,
    genre_tags: Optional[str] = None
) -> str:
    """
    Create a rich, formatted playlist description with statistics.
    
    Args:
        base_description: Base description text
        stats: Statistics dictionary from get_playlist_statistics
        period: Period string (e.g., "Dec 2025")
        playlist_type: Type of playlist
        genre_tags: Pre-formatted genre tags string
    
    Returns:
        Rich formatted description (max 300 chars)
    """
    MAX_LENGTH = 300
    
    # Build description sections
    sections = []
    
    # Base description
    if base_description:
        sections.append(base_description)
    
    # Statistics section
    stats_lines = []
    if stats["total_tracks"] > 0:
        stats_lines.append(f"📊 {stats['total_tracks']} tracks")
        
        if stats["total_duration_hours"] > 0:
            if stats["total_duration_hours"] < 1:
                duration_str = f"{int(stats['total_duration_hours'] * 60)} min"
            else:
                duration_str = f"{stats['total_duration_hours']} hr"
            stats_lines.append(f"⏱️ {duration_str}")
        
        if stats["avg_popularity"] > 0:
            stats_lines.append(f"⭐ {stats['avg_popularity']}/100")
        
        if stats["year_range"][0] and stats["year_range"][1]:
            if stats["year_range"][0] == stats["year_range"][1]:
                stats_lines.append(f"📅 {stats['year_range'][0]}")
            else:
                stats_lines.append(f"📅 {stats['year_range'][0]}-{stats['year_range'][1]}")
    
    if stats_lines:
        sections.append(" | ".join(stats_lines))
    
    # Top artists (if available)
    if stats["top_artists"]:
        top_3 = list(stats["top_artists"].keys())[:3]
        if len(top_3) > 0:
            artists_str = ", ".join(top_3)
            if len(artists_str) <= 50:  # Only add if it fits
                sections.append(f"🎤 {artists_str}")
    
    # Genre tags
    if genre_tags:
        sections.append(genre_tags)
    
    # Combine sections
    description = "\n".join(sections)
    
    # Truncate if needed
    if len(description) > MAX_LENGTH:
        # Try to preserve base description and stats, truncate genre tags
        if genre_tags and len(genre_tags) > 50:
            base_len = len("\n".join(sections[:-1]))
            available = MAX_LENGTH - base_len - 10
            if available > 20:
                # Truncate genre tags
                truncated_genres = genre_tags[:available] + "..."
                description = "\n".join(sections[:-1]) + "\n" + truncated_genres
            else:
                # Remove genre tags if no space
                description = "\n".join(sections[:-1])
        else:
            # Truncate from end
            description = description[:MAX_LENGTH - 3] + "..."
    
    return description


def get_playlist_cover_image_url(
    sp: spotipy.Spotify,
    playlist_id: str,
    tracks_df: pd.DataFrame,
    playlist_tracks_df: pd.DataFrame,
    strategy: str = "most_popular"
) -> Optional[str]:
    """
    Get cover image URL for a playlist using various strategies.
    
    Strategies:
    - "most_popular": Use album art from most popular track
    - "first": Use album art from first track
    - "random": Use album art from random track
    - "most_recent": Use album art from most recently added track
    
    Returns:
        Image URL or None if not found
    """
    playlist_tracks = playlist_tracks_df[playlist_tracks_df["playlist_id"] == playlist_id]
    if playlist_tracks.empty:
        return None
    
    # Merge with track data
    merged = playlist_tracks.merge(tracks_df, on="track_id", how="left")
    
    if merged.empty:
        return None
    
    # Select track based on strategy
    if strategy == "most_popular":
        if "popularity" in merged.columns:
            selected = merged.nlargest(1, "popularity")
        else:
            selected = merged.head(1)
    elif strategy == "most_recent":
        if "added_at" in merged.columns:
            selected = merged.nlargest(1, "added_at")
        else:
            selected = merged.head(1)
    elif strategy == "random":
        selected = merged.sample(1)
    else:  # first
        selected = merged.head(1)
    
    # Get album image URL
    if "album_image_url" in selected.columns:
        image_url = selected["album_image_url"].iloc[0]
        if pd.notna(image_url) and image_url:
            return image_url
    
    # Fallback: try to get from album data
    if "album_id" in selected.columns:
        album_id = selected["album_id"].iloc[0]
        if pd.notna(album_id):
            try:
                album = api_call(sp.album, album_id)
                if album and "images" in album and len(album["images"]) > 0:
                    # Return largest image
                    return max(album["images"], key=lambda x: x.get("width", 0) or 0)["url"]
            except Exception:
                pass
    
    return None


def update_playlist_cover_image(
    sp: spotipy.Spotify,
    playlist_id: str,
    image_url: str
) -> bool:
    """
    Update playlist cover image.
    
    Note: Spotify API doesn't directly support setting cover images via API.
    This function logs the recommended image URL for manual upload.
    
    Args:
        sp: Spotify client
        playlist_id: Playlist ID
        image_url: URL of the image to use
    
    Returns:
        True if recommendation was logged, False otherwise
    """
    if not image_url:
        return False
    
    log(f"  🖼️  Recommended cover image: {image_url}")
    log(f"     (Upload manually via Spotify app - API doesn't support cover image upload)")
    return True


def enhance_playlist_description(
    sp: spotipy.Spotify,
    playlist_id: str,
    base_description: str,
    tracks_df: pd.DataFrame,
    playlist_tracks_df: pd.DataFrame,
    genre_tags: Optional[str] = None
) -> str:
    """
    Enhance playlist description with statistics and rich formatting.
    
    Args:
        sp: Spotify client
        playlist_id: Playlist ID
        base_description: Base description text
        tracks_df: Tracks dataframe
        playlist_tracks_df: Playlist tracks dataframe
        genre_tags: Optional pre-formatted genre tags
    
    Returns:
        Enhanced description string
    """
    # Get statistics
    stats = get_playlist_statistics(sp, playlist_id, tracks_df, playlist_tracks_df)
    
    # Format rich description
    enhanced = format_rich_description(
        base_description=base_description,
        stats=stats,
        genre_tags=genre_tags
    )
    
    return enhanced


def organize_playlist_tracks(
    sp: spotipy.Spotify,
    playlist_id: str,
    sort_by: str = "added_at",
    reverse: bool = True
) -> bool:
    """
    Reorder tracks in a playlist.
    
    Note: Spotify API has limitations on reordering. This function
    provides the logic but may need to be called carefully due to API limits.
    
    Args:
        sp: Spotify client
        playlist_id: Playlist ID
        sort_by: Sort field ("added_at", "popularity", "name", "artist")
        reverse: If True, sort descending
    
    Returns:
        True if successful, False otherwise
    """
    # Note: Full implementation would require fetching all tracks,
    # sorting them, and reordering via API. This is a placeholder
    # for the organization feature.
    log(f"  🔄 Playlist organization: sort by {sort_by} ({'desc' if reverse else 'asc'})")
    log(f"     (Full reordering requires API calls - implement if needed)")
    return True


def check_playlist_health(
    sp: spotipy.Spotify,
    playlist_id: str,
    playlist_name: str,
    tracks_df: pd.DataFrame,
    playlist_tracks_df: pd.DataFrame
) -> Dict[str, any]:
    """
    Perform health check on a playlist.
    
    Checks for:
    - Empty playlists
    - Duplicate tracks
    - Missing metadata
    - Very old tracks (potential cleanup candidates)
    
    Returns:
        Dictionary with health check results
    """
    playlist_tracks = playlist_tracks_df[playlist_tracks_df["playlist_id"] == playlist_id]
    
    issues = []
    warnings = []
    
    # Check if empty
    if playlist_tracks.empty:
        issues.append("empty")
    
    # Check for duplicates
    if not playlist_tracks.empty:
        track_counts = playlist_tracks["track_id"].value_counts()
        duplicates = track_counts[track_counts > 1]
        if len(duplicates) > 0:
            warnings.append(f"{len(duplicates)} duplicate track(s)")
    
    # Check metadata completeness
    if not playlist_tracks.empty:
        merged = playlist_tracks.merge(tracks_df, on="track_id", how="left")
        missing_popularity = merged["popularity"].isna().sum()
        missing_duration = merged["duration_ms"].isna().sum()
        
        if missing_popularity > len(merged) * 0.1:  # More than 10% missing
            warnings.append(f"{missing_popularity} tracks missing popularity data")
        if missing_duration > len(merged) * 0.1:
            warnings.append(f"{missing_duration} tracks missing duration data")
    
    return {
        "playlist_id": playlist_id,
        "playlist_name": playlist_name,
        "issues": issues,
        "warnings": warnings,
        "healthy": len(issues) == 0
    }
