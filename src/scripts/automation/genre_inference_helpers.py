"""
Genre Inference Helper Functions

Extracted from sync.py to improve code organization and maintainability.
These functions handle the complex logic of genre inference with smart caching.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Set, Optional, Tuple
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import multiprocessing as mp
import os

from src.features.genre_inference import infer_genres_comprehensive, enhance_artist_genres_from_playlists
from src.scripts.automation.config import DATA_DIR, PARALLEL_MIN_TRACKS, PARALLEL_MAX_WORKERS
from src.scripts.automation.error_handling import handle_errors
from src.scripts.common.config_helpers import parse_bool_env


def needs_genres(genres_val) -> bool:
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
    
    # Check if NaN (but only for scalar values)
    try:
        scalar_check = pd.api.types.is_scalar(genres_val)
        if scalar_check:
            if pd.isna(genres_val):
                return True
    except (ValueError, TypeError):
        pass
    
    # For other types (including arrays), try to check length
    try:
        if hasattr(genres_val, '__len__'):
            return len(genres_val) == 0
    except (TypeError, AttributeError):
        pass
    
    # Unknown type - treat as needing genres
    return True


def has_valid_genres(genres_val) -> bool:
    """Check if track has valid genres."""
    if genres_val is None or pd.isna(genres_val):
        return False
    if isinstance(genres_val, list):
        return len(genres_val) > 0
    if isinstance(genres_val, (np.ndarray, pd.Series)):
        return len(genres_val) > 0
    return bool(genres_val)


def load_data_files() -> Optional[Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]]:
    """
    Load all required data files for genre inference.
    
    Returns:
        Tuple of (tracks, track_artists, artists, playlist_tracks, playlists) or None on error
    """
    tracks_path = DATA_DIR / "tracks.parquet"
    track_artists_path = DATA_DIR / "track_artists.parquet"
    artists_path = DATA_DIR / "artists.parquet"
    playlist_tracks_path = DATA_DIR / "playlist_tracks.parquet"
    playlists_path = DATA_DIR / "playlists.parquet"
    
    if not all(p.exists() for p in [tracks_path, track_artists_path, artists_path, playlist_tracks_path, playlists_path]):
        return None
    
    try:
        # Try pyarrow first for speed
        tracks = pd.read_parquet(tracks_path, engine='pyarrow')
        track_artists = pd.read_parquet(track_artists_path, engine='pyarrow')
        artists = pd.read_parquet(artists_path, engine='pyarrow')
        playlist_tracks = pd.read_parquet(playlist_tracks_path, engine='pyarrow')
        playlists = pd.read_parquet(playlists_path, engine='pyarrow')
    except Exception:
        # Fallback to default engine
        tracks = pd.read_parquet(tracks_path)
        track_artists = pd.read_parquet(track_artists_path)
        artists = pd.read_parquet(artists_path)
        playlist_tracks = pd.read_parquet(playlist_tracks_path)
        playlists = pd.read_parquet(playlists_path)
    
    # Ensure genres column exists
    if "genres" not in tracks.columns:
        tracks["genres"] = None
    
    return tracks, track_artists, artists, playlist_tracks, playlists


def identify_tracks_needing_inference(
    tracks: pd.DataFrame,
    playlist_tracks: pd.DataFrame,
    stats: Optional[dict] = None
) -> Set[str]:
    """
    Identify which tracks need genre inference.
    
    Args:
        tracks: DataFrame with tracks data
        playlist_tracks: DataFrame with playlist-track relationships
        stats: Optional sync statistics
    
    Returns:
        Set of track IDs that need genre inference
    """
    tracks_needing_inference = set()
    
    # 1. Tracks without genres
    tracks_without_genres = tracks[tracks["genres"].apply(needs_genres)]
    tracks_needing_inference.update(tracks_without_genres["track_id"].tolist())
    
    # 2. New tracks added in this sync (if stats provided)
    if stats and stats.get("tracks_added", 0) > 0:
        playlist_track_ids = set(playlist_tracks["track_id"].unique())
        tracks_with_genres = set(tracks[tracks["genres"].apply(has_valid_genres)]["track_id"].tolist())
        new_track_ids = playlist_track_ids - tracks_with_genres
        tracks_needing_inference.update(new_track_ids)
    
    return tracks_needing_inference


def enhance_artist_genres_if_needed(
    artists: pd.DataFrame,
    track_artists: pd.DataFrame,
    playlist_tracks: pd.DataFrame,
    playlists: pd.DataFrame,
    stats: Optional[dict] = None,
    tracks_with_genres_pct: float = 0.0
) -> Tuple[pd.DataFrame, Set[str]]:
    """
    Enhance artist genres from playlist patterns if needed.
    
    Args:
        artists: DataFrame with artists data
        track_artists: DataFrame with track-artist relationships
        playlist_tracks: DataFrame with playlist-track relationships
        playlists: DataFrame with playlists data
        stats: Optional sync statistics
        tracks_with_genres_pct: Percentage of tracks that already have genres
    
    Returns:
        Tuple of (enhanced_artists_df, set_of_enhanced_artist_ids)
    """
    enhanced_artist_ids = set()
    
    # Skip if most tracks already have genres
    if tracks_with_genres_pct >= 90:
        return artists, enhanced_artist_ids
    
    # Skip if no playlist changes
    if not stats or (stats.get("playlists_updated", 0) == 0 and stats.get("tracks_added", 0) == 0):
        return artists, enhanced_artist_ids
    
    # Check if too many artists without genres
    artists_without_genres = artists[artists["genres"].apply(needs_genres)]
    if len(artists_without_genres) > 500:
        return artists, enhanced_artist_ids
    
    # Enhance artist genres
    artists_before = artists.copy()
    artists_enhanced = enhance_artist_genres_from_playlists(
        artists, track_artists, playlist_tracks, playlists
    )
    
    # Find which artists were enhanced
    artists_dict_before = artists_before.set_index("artist_id")["genres"].to_dict()
    artists_dict_after = artists_enhanced.set_index("artist_id")["genres"].to_dict()
    
    for artist_id in artists_dict_after.keys():
        from src.scripts.automation.sync import _parse_genres
        old_genres = set(_parse_genres(artists_dict_before.get(artist_id, [])))
        new_genres = set(_parse_genres(artists_dict_after.get(artist_id, [])))
        if old_genres != new_genres:
            enhanced_artist_ids.add(artist_id)
    
    # Save enhanced artists if any were enhanced
    if enhanced_artist_ids:
        artists_path = DATA_DIR / "artists.parquet"
        artists_enhanced.to_parquet(artists_path, index=False)
    
    return artists_enhanced, enhanced_artist_ids


def infer_genres_for_track_batch(
    track_data_list: List[Dict],
    track_artists: pd.DataFrame,
    artists: pd.DataFrame,
    playlist_tracks: pd.DataFrame,
    playlists: pd.DataFrame,
    use_parallel: bool = True
) -> Dict[str, List[str]]:
    """
    Infer genres for a batch of tracks (parallel or sequential).
    
    Args:
        track_data_list: List of track data dictionaries
        track_artists: DataFrame with track-artist relationships
        artists: DataFrame with artists data
        playlist_tracks: DataFrame with playlist-track relationships
        playlists: DataFrame with playlists data
        use_parallel: Whether to use parallel processing
    
    Returns:
        Dictionary mapping track_id to list of inferred genres
    """
    inferred_genres_map = {}
    
    if use_parallel:
        num_workers = int(os.environ.get("GENRE_INFERENCE_WORKERS", min(mp.cpu_count() or 4, PARALLEL_MAX_WORKERS)))
        
        def _process_track(track_data):
            """Process a single track's genre inference."""
            try:
                track_id = track_data['track_id']
                track_name = track_data.get('track_name')
                album_name = track_data.get('album_name')
                
                genres = infer_genres_comprehensive(
                    track_id=track_id,
                    track_name=track_name,
                    album_name=album_name,
                    track_artists=track_artists,
                    artists=artists,
                    playlist_tracks=playlist_tracks,
                    playlists=playlists,
                    mode="broad"  # Use broad genres - only ONE broad genre per track
                )
                return (track_id, genres)
            except Exception:
                return (track_data.get('track_id', ''), [])
        
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = {executor.submit(_process_track, track_data): track_data['track_id'] 
                      for track_data in track_data_list}
            
            with tqdm(total=len(track_data_list), desc="  Inferring genres", unit="track", 
                     ncols=100, leave=False) as pbar:
                for future in as_completed(futures):
                    try:
                        track_id, genres = future.result(timeout=30)
                        inferred_genres_map[track_id] = genres
                    except Exception:
                        track_id = futures[future]
                        inferred_genres_map[track_id] = []
                    finally:
                        pbar.update(1)
    else:
        # Sequential processing
        for track_data in tqdm(track_data_list, desc="  Inferring genres", unit="track", 
                              ncols=100, leave=False):
            track_id = track_data['track_id']
            track_name = track_data.get('track_name')
            album_name = track_data.get('album_name')
            
            try:
                genres = infer_genres_comprehensive(
                    track_id=track_id,
                    track_name=track_name,
                    album_name=album_name,
                    track_artists=track_artists,
                    artists=artists,
                    playlist_tracks=playlist_tracks,
                    playlists=playlists,
                    mode="broad"  # Use broad genres - only ONE broad genre per track
                )
                inferred_genres_map[track_id] = genres
            except Exception:
                inferred_genres_map[track_id] = []
    
    return inferred_genres_map


def update_tracks_with_inferred_genres(tracks: pd.DataFrame, inferred_genres_map: Dict[str, List[str]]) -> None:
    """
    Update tracks DataFrame with inferred genres and save to disk.
    
    Args:
        tracks: DataFrame with tracks data
        inferred_genres_map: Dictionary mapping track_id to list of genres
    """
    if not inferred_genres_map:
        return
    
    # Build index map for faster lookups
    track_id_to_row_idx = {}
    for idx, track_id in tracks['track_id'].items():
        if track_id in inferred_genres_map:
            track_id_to_row_idx[track_id] = idx
    
    # Batch update
    for track_id, genres in inferred_genres_map.items():
        if track_id in track_id_to_row_idx:
            tracks.at[track_id_to_row_idx[track_id], "genres"] = genres
    
    # Save updated tracks
    tracks_path = DATA_DIR / "tracks.parquet"
    try:
        tracks.to_parquet(tracks_path, index=False, engine='pyarrow')
    except Exception:
        tracks.to_parquet(tracks_path, index=False)
