"""
Notebook helper functions for spotim8 analysis notebooks.

This module contains all the analysis logic extracted from the notebooks,
allowing notebooks to be simple demonstration scripts that call these functions.
"""

import os
import json
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional, Any
from collections import defaultdict, Counter
import warnings

import pandas as pd
import numpy as np
from tqdm.auto import tqdm

# Add project root to path if not already there
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from spotim8 import Spotim8, set_response_cache
from spotim8.core.catalog import CacheConfig
from spotim8.analysis.analysis import LibraryAnalyzer, PlaylistSimilarityEngine
from spotim8.analysis.streaming_history import (
    sync_all_export_data,
    load_streaming_history,
    load_search_queries_cached,
    load_wrapped_data_cached,
    load_follow_data_cached,
    load_library_snapshot_cached,
    load_playback_errors_cached,
    load_playback_retries_cached,
    load_webapi_events_cached,
)

warnings.filterwarnings('ignore')


# ============================================================================
# Setup & Configuration Functions
# ============================================================================

def setup_project(project_root: Optional[Path] = None) -> Path:
    """Setup project root and return the path."""
    if project_root is None:
        project_root = Path("..").resolve()
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    print(f"✅ Project root: {project_root}")
    return project_root


def setup_credentials(project_root: Path) -> bool:
    """Load and verify Spotify credentials from .env file."""
    from dotenv import load_dotenv
    
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✅ Loaded credentials from {env_path}")
    else:
        print(f"⚠️  No .env file found at {env_path}")
        print("   Create one with SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET, SPOTIPY_REDIRECT_URI")
        return False
    
    client_id = os.environ.get("SPOTIPY_CLIENT_ID", "")
    if client_id and client_id != "YOUR_CLIENT_ID":
        print(f"   Client ID: {client_id[:8]}...")
        return True
    else:
        print("   ❌ SPOTIPY_CLIENT_ID not set!")
        return False


def setup_spotify_client(project_root: Path, progress: bool = True, cache_ttl: int = 3600) -> Spotim8:
    """Initialize and return a Spotim8 client with caching enabled."""
    data_dir = project_root / "data"
    data_dir.mkdir(exist_ok=True)
    
    api_cache_dir = data_dir / ".api_cache"
    set_response_cache(api_cache_dir, ttl=cache_ttl)
    
    sf = Spotim8.from_env(
        progress=progress,
        cache=CacheConfig(dir=data_dir)
    )
    
    print(f"✅ Connected to Spotify!")
    print(f"📁 Data will be saved to: {data_dir}")
    return sf


# ============================================================================
# Notebook 01: Sync Data
# ============================================================================

def sync_spotify_library(sf: Spotim8, sync_export_data: bool = True) -> Dict[str, Any]:
    """Sync Spotify library and optionally export data."""
    print("🔄 Starting library sync...")
    
    # Sync main library
    sf.sync()
    
    results = {
        'library_synced': True,
        'export_data_synced': False
    }
    
    # Optionally sync export data
    if sync_export_data:
        data_dir = sf.data_dir
        print("\n📦 Syncing export data...")
        try:
            sync_all_export_data(data_dir, project_root=PROJECT_ROOT)
            results['export_data_synced'] = True
            print("✅ Export data sync complete!")
        except Exception as e:
            print(f"⚠️  Export data sync failed: {e}")
            print("   (This is optional - you can continue without export data)")
    
    return results


# ============================================================================
# Notebook 02: Analyze Library
# ============================================================================

def analyze_library(
    data_dir: Path,
    exclude_liked_songs: bool = True,
    exclude_monthly: bool = False,
    include_only: Optional[List[str]] = None,
    exclude_names: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Perform comprehensive library analysis."""
    analyzer = LibraryAnalyzer(data_dir).load()
    analyzer.filter(
        exclude_liked=exclude_liked_songs,
        exclude_monthly=exclude_monthly,
        include_only=include_only,
        exclude_names=exclude_names
    )
    
    return {
        'analyzer': analyzer,
        'playlists': analyzer.playlists,
        'tracks': analyzer.tracks,
        'artists': analyzer.artists,
        'playlist_tracks': analyzer.playlist_tracks,
        'track_artists': analyzer.track_artists,
    }


def generate_library_statistics(analyzer: LibraryAnalyzer) -> Dict[str, Any]:
    """Generate library statistics and summaries."""
    playlists = analyzer.playlists
    tracks = analyzer.tracks
    artists = analyzer.artists
    
    stats = {
        'total_playlists': len(playlists),
        'total_tracks': len(tracks),
        'total_artists': len(artists),
        'total_unique_tracks': len(tracks['track_id'].unique()) if len(tracks) > 0 else 0,
    }
    
    if len(playlists) > 0:
        stats['playlist_size_stats'] = {
            'mean': playlists['track_count'].mean(),
            'median': playlists['track_count'].median(),
            'min': playlists['track_count'].min(),
            'max': playlists['track_count'].max(),
        }
    
    return stats


# ============================================================================
# Notebook 03: Playlist Analysis
# ============================================================================

def build_playlist_genre_profiles(analyzer: LibraryAnalyzer) -> pd.DataFrame:
    """Build genre profiles for all playlists."""
    from spotim8.analysis import build_playlist_genre_profiles as _build
    return _build(analyzer)


def analyze_playlist_similarity(
    analyzer: LibraryAnalyzer,
    search_mode: str = "followed_only"
) -> PlaylistSimilarityEngine:
    """Analyze playlist similarity and return similarity engine."""
    from spotim8.analysis import PlaylistSimilarityEngine
    
    similarity_engine = PlaylistSimilarityEngine(analyzer)
    
    if search_mode == "followed_only":
        search_playlists = analyzer.playlists_all[analyzer.playlists_all['is_owned'] == False]
    elif search_mode == "owned_only":
        search_playlists = analyzer.playlists_all[analyzer.playlists_all['is_owned'] == True]
    else:  # "all"
        search_playlists = analyzer.playlists_all
    
    return similarity_engine


# ============================================================================
# Notebook 04: Listening History Analysis
# ============================================================================

def analyze_listening_history(
    data_dir: Path,
    project_root: Optional[Path] = None
) -> Dict[str, pd.DataFrame]:
    """Load and return all listening history data."""
    if project_root is None:
        project_root = PROJECT_ROOT
    
    results = {}
    
    # Load streaming history
    try:
        results['streaming_history'] = load_streaming_history(data_dir)
    except Exception as e:
        print(f"⚠️  Could not load streaming history: {e}")
        results['streaming_history'] = None
    
    # Load other export data
    try:
        results['search_queries'] = load_search_queries_cached(data_dir)
        results['wrapped_data'] = load_wrapped_data_cached(data_dir)
        results['follow_data'] = load_follow_data_cached(data_dir)
        results['library_snapshot'] = load_library_snapshot_cached(data_dir)
    except Exception as e:
        print(f"⚠️  Could not load some export data: {e}")
    
    return results


def analyze_listening_patterns(
    streaming_history: pd.DataFrame,
    library_analyzer: Optional[LibraryAnalyzer] = None
) -> Dict[str, Any]:
    """Analyze listening patterns from streaming history."""
    if streaming_history is None or len(streaming_history) == 0:
        return {'error': 'No streaming history data available'}
    
    patterns = {
        'total_plays': len(streaming_history),
        'unique_tracks': streaming_history['track_id'].nunique() if 'track_id' in streaming_history.columns else 0,
        'unique_artists': streaming_history['artist_id'].nunique() if 'artist_id' in streaming_history.columns else 0,
    }
    
    if 'played_at' in streaming_history.columns:
        streaming_history['played_at'] = pd.to_datetime(streaming_history['played_at'])
        patterns['date_range'] = {
            'start': streaming_history['played_at'].min(),
            'end': streaming_history['played_at'].max(),
        }
        
        # Time of day patterns
        streaming_history['hour'] = streaming_history['played_at'].dt.hour
        patterns['hourly_distribution'] = streaming_history['hour'].value_counts().sort_index().to_dict()
        
        # Day of week patterns
        streaming_history['day_of_week'] = streaming_history['played_at'].dt.day_name()
        patterns['daily_distribution'] = streaming_history['day_of_week'].value_counts().to_dict()
    
    return patterns


# ============================================================================
# Notebook 05: Liked Songs Monthly Playlists
# ============================================================================

def preview_monthly_playlists(
    analyzer: LibraryAnalyzer,
    owner_name: str,
    prefix: str,
    monthly_template: str,
    genre_split: bool = True,
    genre_template: Optional[str] = None
) -> Dict[str, Any]:
    """Preview what monthly playlists would be created."""
    # This is a simplified preview - actual implementation would use sync.py logic
    return {
        'preview': 'Monthly playlist preview not yet implemented in helper module',
        'note': 'Use scripts/sync.py for actual playlist creation'
    }


# ============================================================================
# Notebook 06: Identify Redundant Playlists
# ============================================================================

def jaccard_similarity(set1: Set, set2: Set) -> float:
    """Calculate Jaccard similarity (intersection / union)."""
    if not set1 and not set2:
        return 1.0
    if not set1 or not set2:
        return 0.0
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    return intersection / union if union > 0 else 0.0


def overlap_ratio(set1: Set, set2: Set) -> Tuple[float, float]:
    """Calculate overlap ratios in both directions."""
    if not set1 or not set2:
        return (0.0, 0.0)
    intersection = len(set1 & set2)
    return (intersection / len(set1), intersection / len(set2))


def is_auto_generated_playlist(name: str) -> bool:
    """Check if playlist is auto-generated (starts with 'AJ')."""
    return name.startswith('AJ') if name else False


def identify_redundant_playlists(
    data_dir: Path,
    exclude_auto_generated: bool = True
) -> Dict[str, Any]:
    """Identify redundant playlists with aggressive thresholds."""
    analyzer = LibraryAnalyzer(data_dir).load()
    
    # Get owned playlists
    playlists = analyzer.playlists_all[analyzer.playlists_all['is_owned'] == True].copy()
    playlist_tracks = analyzer.playlist_tracks_all[
        analyzer.playlist_tracks_all['playlist_id'].isin(playlists['playlist_id'])
    ].copy()
    
    # Exclude Liked Songs
    liked_id = analyzer.liked_songs_id
    if liked_id:
        playlists = playlists[playlists['playlist_id'] != liked_id].copy()
    
    # Exclude auto-generated playlists
    excluded_ids = set()
    if exclude_auto_generated:
        auto_generated = playlists[playlists['name'].str.startswith('AJ', na=False)].copy()
        excluded_ids = set(auto_generated['playlist_id'].tolist())
        playlists = playlists[~playlists['playlist_id'].isin(excluded_ids)].copy()
    
    # Build track sets
    playlist_track_sets: Dict[str, Set[str]] = {}
    playlist_info = {}
    
    for pid in playlists['playlist_id']:
        info = playlists[playlists['playlist_id'] == pid].iloc[0]
        playlist_name = info.get('name', 'Unknown')
        
        if exclude_auto_generated and is_auto_generated_playlist(playlist_name):
            continue
        
        tracks = set(playlist_tracks[playlist_tracks['playlist_id'] == pid]['track_id'].unique())
        playlist_track_sets[pid] = tracks
        playlist_info[pid] = {
            'name': playlist_name,
            'track_count': len(tracks),
            'is_liked_songs': info.get('is_liked_songs', False),
        }
    
    # Analyze redundancy
    playlist_ids = list(playlist_track_sets.keys())
    exact_duplicates = []
    subsets = []
    high_overlap = []
    near_duplicates = []
    merge_candidates = []
    similar_playlists = []
    
    print(f"🔍 Analyzing {len(playlist_ids)} playlists...")
    for i in tqdm(range(len(playlist_ids)), desc="Comparing playlists"):
        pid1 = playlist_ids[i]
        set1 = playlist_track_sets[pid1]
        
        if not set1:
            continue
        
        for j in range(i + 1, len(playlist_ids)):
            pid2 = playlist_ids[j]
            set2 = playlist_track_sets[pid2]
            
            if not set2:
                continue
            
            # Exact duplicates
            if set1 == set2:
                exact_duplicates.append((pid1, pid2))
                continue
            
            # Subsets
            if set1.issubset(set2):
                subsets.append((pid1, pid2, len(set1), len(set2)))
            elif set2.issubset(set1):
                subsets.append((pid2, pid1, len(set2), len(set1)))
            
            # Calculate similarity
            jaccard = jaccard_similarity(set1, set2)
            overlap1, overlap2 = overlap_ratio(set1, set2)
            
            if jaccard > 0.7:
                high_overlap.append((pid1, pid2, jaccard, overlap1, overlap2))
            elif jaccard > 0.5:
                near_duplicates.append((pid1, pid2, jaccard, overlap1, overlap2))
            elif jaccard > 0.4:
                similar_playlists.append((pid1, pid2, jaccard, overlap1, overlap2))
            
            # Merge candidates
            size1, size2 = len(set1), len(set2)
            if size1 > 0 and size2 > 0:
                if size2 >= 3 * size1 and overlap1 > 0.5:
                    merge_candidates.append((pid1, pid2, overlap1, overlap2, size1, size2))
                elif size1 >= 3 * size2 and overlap2 > 0.5:
                    merge_candidates.append((pid2, pid1, overlap2, overlap1, size2, size1))
    
    return {
        'playlist_track_sets': playlist_track_sets,
        'playlist_info': playlist_info,
        'exact_duplicates': exact_duplicates,
        'subsets': subsets,
        'high_overlap': high_overlap,
        'near_duplicates': near_duplicates,
        'merge_candidates': merge_candidates,
        'similar_playlists': similar_playlists,
        'excluded_count': len(excluded_ids),
    }


def build_consolidation_suggestions(
    redundancy_results: Dict[str, Any],
    exclude_auto_generated: bool = True
) -> Dict[str, Any]:
    """Build comprehensive consolidation suggestions."""
    playlist_track_sets = redundancy_results['playlist_track_sets']
    playlist_info = redundancy_results['playlist_info']
    exact_duplicates = redundancy_results['exact_duplicates']
    subsets = redundancy_results['subsets']
    high_overlap = redundancy_results['high_overlap']
    near_duplicates = redundancy_results['near_duplicates']
    merge_candidates = redundancy_results['merge_candidates']
    
    safe_to_delete = set()
    consolidation_suggestions = []
    
    # 1. Exact duplicates
    for pid1, pid2 in exact_duplicates:
        if exclude_auto_generated and (
            is_auto_generated_playlist(playlist_info.get(pid1, {}).get('name', '')) or
            is_auto_generated_playlist(playlist_info.get(pid2, {}).get('name', ''))
        ):
            continue
        info1 = playlist_info[pid1]
        info2 = playlist_info[pid2]
        if len(info1['name']) >= len(info2['name']):
            safe_to_delete.add(pid2)
            consolidation_suggestions.append({
                'action': 'delete',
                'playlist_id': pid2,
                'playlist_name': info2['name'],
                'reason': f'Exact duplicate of "{info1["name"]}"',
                'tracks_lost': 0,
                'alternative': info1['name']
            })
        else:
            safe_to_delete.add(pid1)
            consolidation_suggestions.append({
                'action': 'delete',
                'playlist_id': pid1,
                'playlist_name': info1['name'],
                'reason': f'Exact duplicate of "{info2["name"]}"',
                'tracks_lost': 0,
                'alternative': info2['name']
            })
    
    # 2. Subsets
    for subset_pid, superset_pid, subset_size, superset_size in subsets:
        if exclude_auto_generated and (
            is_auto_generated_playlist(playlist_info.get(subset_pid, {}).get('name', '')) or
            is_auto_generated_playlist(playlist_info.get(superset_pid, {}).get('name', ''))
        ):
            continue
        if subset_pid not in safe_to_delete:
            subset_info = playlist_info[subset_pid]
            superset_info = playlist_info[superset_pid]
            safe_to_delete.add(subset_pid)
            consolidation_suggestions.append({
                'action': 'delete',
                'playlist_id': subset_pid,
                'playlist_name': subset_info['name'],
                'reason': f'All {subset_size} tracks are in "{superset_info["name"]}" ({superset_size} tracks)',
                'tracks_lost': 0,
                'alternative': superset_info['name']
            })
    
    # 3. High overlap
    for pid1, pid2, jaccard, overlap1, overlap2 in high_overlap:
        if exclude_auto_generated and (
            is_auto_generated_playlist(playlist_info.get(pid1, {}).get('name', '')) or
            is_auto_generated_playlist(playlist_info.get(pid2, {}).get('name', ''))
        ):
            continue
        if pid1 in safe_to_delete or pid2 in safe_to_delete:
            continue
        info1 = playlist_info[pid1]
        info2 = playlist_info[pid2]
        if info1['track_count'] > info2['track_count']:
            keep_pid, delete_pid = pid1, pid2
            keep_info, delete_info = info1, info2
            missing_tracks = len(playlist_track_sets[pid2] - playlist_track_sets[pid1])
            overlap_pct = overlap2 * 100
        else:
            keep_pid, delete_pid = pid2, pid1
            keep_info, delete_info = info2, info1
            missing_tracks = len(playlist_track_sets[pid1] - playlist_track_sets[pid2])
            overlap_pct = overlap1 * 100
        
        if delete_pid not in safe_to_delete:
            safe_to_delete.add(delete_pid)
            consolidation_suggestions.append({
                'action': 'merge',
                'playlist_id': delete_pid,
                'playlist_name': delete_info['name'],
                'reason': f'{jaccard*100:.1f}% similar, {overlap_pct:.1f}% of tracks already in "{keep_info["name"]}"',
                'tracks_lost': missing_tracks,
                'alternative': f'Merge into "{keep_info["name"]}" (add {missing_tracks} missing tracks, zero loss)'
            })
    
    # 4. Near-duplicates
    for pid1, pid2, jaccard, overlap1, overlap2 in near_duplicates:
        if exclude_auto_generated and (
            is_auto_generated_playlist(playlist_info.get(pid1, {}).get('name', '')) or
            is_auto_generated_playlist(playlist_info.get(pid2, {}).get('name', ''))
        ):
            continue
        if pid1 in safe_to_delete or pid2 in safe_to_delete:
            continue
        info1 = playlist_info[pid1]
        info2 = playlist_info[pid2]
        size1, size2 = info1['track_count'], info2['track_count']
        if size2 >= 2 * size1 and overlap1 > 0.5:
            missing_tracks = len(playlist_track_sets[pid1] - playlist_track_sets[pid2])
            if pid1 not in safe_to_delete:
                safe_to_delete.add(pid1)
                consolidation_suggestions.append({
                    'action': 'merge',
                    'playlist_id': pid1,
                    'playlist_name': info1['name'],
                    'reason': f'{jaccard*100:.1f}% similar, {overlap1*100:.1f}% overlap with larger "{info2["name"]}"',
                    'tracks_lost': missing_tracks,
                    'alternative': f'Merge into "{info2["name"]}" (add {missing_tracks} missing tracks, zero loss)'
                })
        elif size1 >= 2 * size2 and overlap2 > 0.5:
            missing_tracks = len(playlist_track_sets[pid2] - playlist_track_sets[pid1])
            if pid2 not in safe_to_delete:
                safe_to_delete.add(pid2)
                consolidation_suggestions.append({
                    'action': 'merge',
                    'playlist_id': pid2,
                    'playlist_name': info2['name'],
                    'reason': f'{jaccard*100:.1f}% similar, {overlap2*100:.1f}% overlap with larger "{info1["name"]}"',
                    'tracks_lost': missing_tracks,
                    'alternative': f'Merge into "{info1["name"]}" (add {missing_tracks} missing tracks, zero loss)'
                })
    
    # 5. Merge candidates
    for small_pid, large_pid, small_overlap, large_overlap, small_size, large_size in merge_candidates:
        if exclude_auto_generated and (
            is_auto_generated_playlist(playlist_info.get(small_pid, {}).get('name', '')) or
            is_auto_generated_playlist(playlist_info.get(large_pid, {}).get('name', ''))
        ):
            continue
        if small_pid not in safe_to_delete:
            small_info = playlist_info[small_pid]
            large_info = playlist_info[large_pid]
            missing_tracks = len(playlist_track_sets[small_pid] - playlist_track_sets[large_pid])
            safe_to_delete.add(small_pid)
            consolidation_suggestions.append({
                'action': 'merge',
                'playlist_id': small_pid,
                'playlist_name': small_info['name'],
                'reason': f'Small playlist ({small_size} tracks) with {small_overlap*100:.1f}% overlap in larger "{large_info["name"]}" ({large_size} tracks)',
                'tracks_lost': missing_tracks,
                'alternative': f'Merge into "{large_info["name"]}" (add {missing_tracks} missing tracks, zero loss)'
            })
    
    return {
        'safe_to_delete': safe_to_delete,
        'consolidation_suggestions': consolidation_suggestions,
    }


def build_consolidation_strategies(
    redundancy_results: Dict[str, Any],
    consolidation_results: Dict[str, Any]
) -> Dict[str, Any]:
    """Build consolidation strategies for similar playlists."""
    playlist_track_sets = redundancy_results['playlist_track_sets']
    playlist_info = redundancy_results['playlist_info']
    similar_playlists = redundancy_results['similar_playlists']
    safe_to_delete = consolidation_results['safe_to_delete']
    
    similar_consolidation_candidates = []
    
    for pid1, pid2, jaccard, overlap1, overlap2 in similar_playlists:
        if (
            is_auto_generated_playlist(playlist_info.get(pid1, {}).get('name', '')) or
            is_auto_generated_playlist(playlist_info.get(pid2, {}).get('name', ''))
        ):
            continue
        if pid1 in safe_to_delete or pid2 in safe_to_delete:
            continue
        
        info1 = playlist_info[pid1]
        info2 = playlist_info[pid2]
        size1, size2 = info1['track_count'], info2['track_count']
        
        missing_1_to_2 = len(playlist_track_sets[pid1] - playlist_track_sets[pid2])
        missing_2_to_1 = len(playlist_track_sets[pid2] - playlist_track_sets[pid1])
        
        if size2 >= 2 * size1 and overlap1 > 0.6:
            strategy = "merge_into_larger"
            recommended_action = f"Merge '{info1['name']}' into '{info2['name']}'"
            tracks_to_add = missing_1_to_2
            confidence = "High" if overlap1 > 0.7 else "Medium"
        elif size1 >= 2 * size2 and overlap2 > 0.6:
            strategy = "merge_into_larger"
            recommended_action = f"Merge '{info2['name']}' into '{info1['name']}'"
            tracks_to_add = missing_2_to_1
            confidence = "High" if overlap2 > 0.7 else "Medium"
        elif abs(size1 - size2) / max(size1, size2, 1) < 0.3 and jaccard > 0.45:
            strategy = "combine"
            overlap_tracks = int(size1 * overlap1 / 100)
            unique_combined = size1 + size2 - overlap_tracks
            recommended_action = f"Create combined playlist with tracks from both '{info1['name']}' and '{info2['name']}'"
            tracks_to_add = missing_1_to_2 + missing_2_to_1
            confidence = "Medium"
        else:
            strategy = "review"
            recommended_action = f"Review for potential consolidation: '{info1['name']}' and '{info2['name']}'"
            tracks_to_add = min(missing_1_to_2, missing_2_to_1)
            confidence = "Low"
        
        unique_combined = None
        if strategy == "combine":
            overlap_tracks = int(size1 * overlap1 / 100)
            unique_combined = size1 + size2 - overlap_tracks
        
        similar_consolidation_candidates.append({
            'playlist1': info1['name'],
            'tracks1': size1,
            'playlist2': info2['name'],
            'tracks2': size2,
            'similarity': jaccard * 100,
            'overlap1': overlap1 * 100,
            'overlap2': overlap2 * 100,
            'missing_1_to_2': missing_1_to_2,
            'missing_2_to_1': missing_2_to_1,
            'strategy': strategy,
            'recommended_action': recommended_action,
            'tracks_to_add': tracks_to_add,
            'unique_combined': unique_combined,
            'confidence': confidence
        })
    
    return {
        'similar_consolidation_candidates': similar_consolidation_candidates,
    }


# ============================================================================
# Notebook 07: Analyze Crashes
# ============================================================================

def analyze_crashes(data_dir: Path) -> Dict[str, pd.DataFrame]:
    """Load and analyze crash/error data."""
    results = {}
    
    try:
        results['playback_errors'] = load_playback_errors_cached(data_dir)
        results['playback_retries'] = load_playback_retries_cached(data_dir)
        results['webapi_events'] = load_webapi_events_cached(data_dir)
    except Exception as e:
        print(f"⚠️  Could not load some crash data: {e}")
    
    return results


def analyze_error_patterns(playback_errors: pd.DataFrame) -> Dict[str, Any]:
    """Analyze patterns in playback errors."""
    if playback_errors is None or len(playback_errors) == 0:
        return {'error': 'No playback error data available'}
    
    patterns = {
        'total_errors': len(playback_errors),
        'fatal_errors': len(playback_errors[playback_errors.get('fatal', False) == True]) if 'fatal' in playback_errors.columns else 0,
        'error_codes': playback_errors['message_error_code'].value_counts().to_dict() if 'message_error_code' in playback_errors.columns else {},
    }
    
    return patterns

