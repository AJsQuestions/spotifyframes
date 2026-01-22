"""
Playlist Organization & Management Module

Provides advanced playlist organization features including:
- Smart sorting and ordering
- Playlist health checks
- Duplicate detection and removal
- Playlist categorization
"""

import spotipy
import pandas as pd
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime, timedelta
from collections import Counter
from pathlib import Path

from .sync import DATA_DIR, api_call, log, verbose_log, get_existing_playlists, get_user_info
from .playlist_aesthetics import check_playlist_health, get_playlist_statistics


def categorize_playlists(playlists_df: pd.DataFrame) -> Dict[str, List[str]]:
    """
    Categorize playlists into logical groups.
    
    Categories:
    - automated: Auto-generated playlists (monthly, yearly, genre)
    - manual: User-created playlists
    - favorites: Liked songs and favorites
    - discovery: Discovery and new music playlists
    - genre: Genre-specific playlists
    - time_based: Time-based playlists (Top, etc.)
    
    Returns:
        Dictionary mapping category to list of playlist IDs
    """
    categories = {
        "automated": [],
        "manual": [],
        "favorites": [],
        "discovery": [],
        "genre": [],
        "time_based": []
    }
    
    for _, playlist in playlists_df.iterrows():
        name = playlist.get("name", "").lower()
        playlist_id = playlist["playlist_id"]
        
        # Check for automated playlists (monthly, yearly patterns)
        if any(keyword in name for keyword in ["finds", "top", "discovery", "dscvr", "fnds"]):
            if any(month in name for month in ["jan", "feb", "mar", "apr", "may", "jun", 
                                               "jul", "aug", "sep", "oct", "nov", "dec"]):
                categories["automated"].append(playlist_id)
            elif any(char.isdigit() for char in name):  # Yearly playlists
                categories["automated"].append(playlist_id)
            else:
                categories["time_based"].append(playlist_id)
        
        # Genre playlists
        elif any(keyword in name for keyword in ["hiphop", "dance", "r&b", "soul", "rock", 
                                                 "pop", "jazz", "country", "electronic"]):
            categories["genre"].append(playlist_id)
        
        # Discovery playlists
        elif any(keyword in name for keyword in ["discovery", "new", "fresh", "latest"]):
            categories["discovery"].append(playlist_id)
        
        # Favorites
        elif any(keyword in name for keyword in ["liked", "favorite", "favourite", "best", "top"]):
            categories["favorites"].append(playlist_id)
        
        # Manual (everything else)
        else:
            categories["manual"].append(playlist_id)
    
    return categories


def find_duplicate_tracks_in_playlist(
    playlist_tracks_df: pd.DataFrame,
    playlist_id: str
) -> List[str]:
    """
    Find duplicate tracks in a single playlist.
    
    Returns:
        List of duplicate track IDs
    """
    playlist_tracks = playlist_tracks_df[playlist_tracks_df["playlist_id"] == playlist_id]
    track_counts = playlist_tracks["track_id"].value_counts()
    duplicates = track_counts[track_counts > 1].index.tolist()
    return duplicates


def find_empty_playlists(
    playlists_df: pd.DataFrame,
    playlist_tracks_df: pd.DataFrame
) -> List[Tuple[str, str]]:
    """
    Find playlists with no tracks.
    
    Returns:
        List of (playlist_id, playlist_name) tuples
    """
    empty = []
    for _, playlist in playlists_df.iterrows():
        playlist_id = playlist["playlist_id"]
        tracks = playlist_tracks_df[playlist_tracks_df["playlist_id"] == playlist_id]
        if tracks.empty:
            empty.append((playlist_id, playlist.get("name", "Unknown")))
    return empty


def find_stale_playlists(
    playlists_df: pd.DataFrame,
    playlist_tracks_df: pd.DataFrame,
    days_threshold: int = 365
) -> List[Tuple[str, str, int]]:
    """
    Find playlists that haven't been updated in a while.
    
    Args:
        days_threshold: Number of days to consider a playlist stale
    
    Returns:
        List of (playlist_id, playlist_name, days_since_update) tuples
    """
    stale = []
    cutoff_date = datetime.now() - timedelta(days=days_threshold)
    
    for _, playlist in playlists_df.iterrows():
        playlist_id = playlist["playlist_id"]
        tracks = playlist_tracks_df[playlist_tracks_df["playlist_id"] == playlist_id]
        
        if not tracks.empty and "added_at" in tracks.columns:
            latest = pd.to_datetime(tracks["added_at"]).max()
            if latest < cutoff_date:
                days_ago = (datetime.now() - latest.to_pydatetime()).days
                stale.append((playlist_id, playlist.get("name", "Unknown"), days_ago))
    
    return stale


def get_playlist_organization_report(
    playlists_df: pd.DataFrame,
    playlist_tracks_df: pd.DataFrame,
    tracks_df: pd.DataFrame
) -> Dict[str, any]:
    """
    Generate comprehensive organization report for all playlists.
    
    Returns:
        Dictionary with organization metrics and recommendations
    """
    categories = categorize_playlists(playlists_df)
    empty_playlists = find_empty_playlists(playlists_df, playlist_tracks_df)
    stale_playlists = find_stale_playlists(playlists_df, playlist_tracks_df)
    
    # Count duplicates across all playlists
    total_duplicates = 0
    playlists_with_duplicates = []
    for _, playlist in playlists_df.iterrows():
        duplicates = find_duplicate_tracks_in_playlist(
            playlist_tracks_df, playlist["playlist_id"]
        )
        if duplicates:
            total_duplicates += len(duplicates)
            playlists_with_duplicates.append(playlist["name"])
    
    # Calculate statistics
    total_playlists = len(playlists_df)
    total_tracks = len(playlist_tracks_df)
    avg_tracks_per_playlist = total_tracks / total_playlists if total_playlists > 0 else 0
    
    return {
        "total_playlists": total_playlists,
        "total_tracks": total_tracks,
        "avg_tracks_per_playlist": round(avg_tracks_per_playlist, 1),
        "categories": {k: len(v) for k, v in categories.items()},
        "empty_playlists": len(empty_playlists),
        "empty_playlist_details": empty_playlists[:10],  # Limit to first 10
        "stale_playlists": len(stale_playlists),
        "stale_playlist_details": stale_playlists[:10],
        "total_duplicates": total_duplicates,
        "playlists_with_duplicates": len(playlists_with_duplicates),
        "playlists_with_duplicates_details": playlists_with_duplicates[:10]
    }


def print_organization_report(report: Dict[str, any]) -> None:
    """Print a formatted organization report."""
    log("\n" + "="*60)
    log("📊 Playlist Organization Report")
    log("="*60)
    
    log(f"\n📋 Overview:")
    log(f"   Total playlists: {report['total_playlists']}")
    log(f"   Total tracks: {report['total_tracks']:,}")
    log(f"   Avg tracks/playlist: {report['avg_tracks_per_playlist']}")
    
    log(f"\n📁 Categories:")
    for category, count in report['categories'].items():
        log(f"   {category.replace('_', ' ').title()}: {count}")
    
    if report['empty_playlists'] > 0:
        log(f"\n⚠️  Empty Playlists: {report['empty_playlists']}")
        for pid, name in report['empty_playlist_details']:
            log(f"   • {name}")
    
    if report['stale_playlists'] > 0:
        log(f"\n⏰ Stale Playlists (>1 year): {report['stale_playlists']}")
        for pid, name, days in report['stale_playlist_details']:
            log(f"   • {name} ({days} days ago)")
    
    if report['total_duplicates'] > 0:
        log(f"\n🔄 Duplicate Tracks: {report['total_duplicates']} across {report['playlists_with_duplicates']} playlists")
        for name in report['playlists_with_duplicates_details']:
            log(f"   • {name}")
    
    log("\n" + "="*60)


def remove_duplicate_tracks_from_playlist(
    sp: spotipy.Spotify,
    playlist_id: str,
    playlist_tracks_df: pd.DataFrame,
    dry_run: bool = True
) -> int:
    """
    Remove duplicate tracks from a playlist, keeping the first occurrence.
    
    Args:
        sp: Spotify client
        playlist_id: Playlist ID
        playlist_tracks_df: Playlist tracks dataframe
        dry_run: If True, only report what would be removed
    
    Returns:
        Number of duplicates removed (or would be removed)
    """
    duplicates = find_duplicate_tracks_in_playlist(playlist_tracks_df, playlist_id)
    
    if not duplicates:
        return 0
    
    # Get all track positions for duplicates
    playlist_tracks = playlist_tracks_df[playlist_tracks_df["playlist_id"] == playlist_id]
    to_remove = []
    
    for track_id in duplicates:
        # Get all occurrences of this track
        occurrences = playlist_tracks[playlist_tracks["track_id"] == track_id]
        # Keep first, remove rest
        if "position" in occurrences.columns:
            positions = sorted(occurrences["position"].tolist())
            to_remove.extend(positions[1:])  # Remove all but first
    
    if not dry_run and to_remove:
        # Note: Spotify API requires track URIs and positions for removal
        # This is a simplified version - full implementation would need
        # to fetch current playlist state and remove by position
        log(f"  Would remove {len(to_remove)} duplicate track(s)")
        return len(to_remove)
    
    return len(to_remove)
