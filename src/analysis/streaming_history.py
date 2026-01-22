"""
Streaming History Data Processing

Loads and processes Spotify data exports (Account Data, Extended History, Technical Logs)
and saves them in a format compatible with the src data catalog.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Dict, Any
import pandas as pd
import numpy as np
from datetime import datetime


def load_basic_streaming_history(account_data_dir: Path) -> Optional[pd.DataFrame]:
    """Load basic streaming history from Account Data folder."""
    files = list(account_data_dir.glob("StreamingHistory_music_*.json"))
    if not files:
        return None
    
    all_streams = []
    for f in sorted(files):
        with open(f, 'r', encoding='utf-8') as fp:
            data = json.load(fp)
            all_streams.extend(data)
    
    if not all_streams:
        return None
    
    df = pd.DataFrame(all_streams)
    
    # Parse datetime
    df['endTime'] = pd.to_datetime(df['endTime'], format='%Y-%m-%d %H:%M')
    df['date'] = df['endTime'].dt.date
    df['hour'] = df['endTime'].dt.hour
    df['day_of_week'] = df['endTime'].dt.day_name()
    df['day_of_week_num'] = df['endTime'].dt.dayofweek
    df['month'] = df['endTime'].dt.to_period('M')
    df['minutes_played'] = df['msPlayed'] / 60000
    
    # Filter out very short plays (likely skips) - at least 30 seconds
    df = df[df['msPlayed'] >= 30000]
    
    # Standardize column names
    df = df.rename(columns={
        'artistName': 'artist_name',
        'trackName': 'track_name',
        'msPlayed': 'ms_played',
        'endTime': 'timestamp'
    })
    
    # Add source indicator
    df['source'] = 'basic'
    
    return df


def load_extended_streaming_history(extended_history_dir: Path) -> Optional[pd.DataFrame]:
    """Load extended streaming history with detailed metadata."""
    files = list(extended_history_dir.glob("Streaming_History_Audio_*.json"))
    if not files:
        return None
    
    all_streams = []
    for f in sorted(files):
        with open(f, 'r', encoding='utf-8') as fp:
            data = json.load(fp)
            all_streams.extend(data)
    
    if not all_streams:
        return None
    
    df = pd.DataFrame(all_streams)
    
    # Parse timestamp
    df['ts'] = pd.to_datetime(df['ts'])
    df['date'] = df['ts'].dt.date
    df['hour'] = df['ts'].dt.hour
    df['day_of_week'] = df['ts'].dt.day_name()
    df['day_of_week_num'] = df['ts'].dt.dayofweek
    df['month'] = df['ts'].dt.to_period('M')
    df['minutes_played'] = df['ms_played'] / 60000
    
    # Filter meaningful plays
    df = df[df['ms_played'] >= 30000]  # At least 30 seconds
    df = df[~df['skipped']]  # Not skipped
    
    # Standardize column names
    df = df.rename(columns={
        'master_metadata_track_name': 'track_name',
        'master_metadata_album_artist_name': 'artist_name',
        'master_metadata_album_album_name': 'album_name',
        'ts': 'timestamp',
        'spotify_track_uri': 'track_uri'
    })
    
    # Add source indicator
    df['source'] = 'extended'
    
    return df


def load_search_queries(account_data_dir: Path) -> Optional[pd.DataFrame]:
    """Load search query history."""
    search_file = account_data_dir / "SearchQueries.json"
    if not search_file.exists():
        return None
    
    with open(search_file, 'r', encoding='utf-8') as fp:
        data = json.load(fp)
    
    if not data:
        return None
    
    df = pd.DataFrame(data)
    
    # Handle datetime format: "2025-10-04T22:39:02.044Z[UTC]" - strip [UTC] part
    if 'searchTime' in df.columns:
        # Remove [UTC] suffix if present, then parse ISO8601 format
        df['searchTime'] = df['searchTime'].astype(str).str.replace(r'\[UTC\]$', '', regex=True)
        df['searchTime'] = pd.to_datetime(df['searchTime'], utc=True, errors='coerce')
        df['date'] = df['searchTime'].dt.date
        df['hour'] = df['searchTime'].dt.hour
        df['month'] = df['searchTime'].dt.to_period('M')
        df = df.rename(columns={'searchTime': 'timestamp'})
    
    return df


def load_wrapped_data(account_data_dir: Path) -> Optional[Dict[str, Any]]:
    """Load Wrapped data (yearly summary)."""
    wrapped_file = account_data_dir / "Wrapped2024.json"
    if not wrapped_file.exists():
        # Try other years
        wrapped_files = list(account_data_dir.glob("Wrapped*.json"))
        if not wrapped_files:
            return None
        wrapped_file = wrapped_files[0]  # Use first found
    
    with open(wrapped_file, 'r', encoding='utf-8') as fp:
        data = json.load(fp)
    
    return data


def load_follow_data(account_data_dir: Path) -> Optional[pd.DataFrame]:
    """Load follow/follower data."""
    follow_file = account_data_dir / "Follow.json"
    if not follow_file.exists():
        return None
    
    with open(follow_file, 'r', encoding='utf-8') as fp:
        data = json.load(fp)
    
    if not data:
        return None
    
    # Convert to DataFrame format
    records = []
    if 'userIsFollowing' in data:
        for user in data['userIsFollowing']:
            records.append({'user': user, 'relationship': 'following'})
    if 'userIsFollowedBy' in data:
        for user in data['userIsFollowedBy']:
            records.append({'user': user, 'relationship': 'followed_by'})
    if 'userIsBlocking' in data:
        for user in data['userIsBlocking']:
            records.append({'user': user, 'relationship': 'blocking'})
    
    if not records:
        return None
    
    return pd.DataFrame(records)


def load_your_library_snapshot(account_data_dir: Path) -> Optional[pd.DataFrame]:
    """Load YourLibrary.json snapshot."""
    library_file = account_data_dir / "YourLibrary.json"
    if not library_file.exists():
        return None
    
    try:
        with open(library_file, 'r', encoding='utf-8') as fp:
            data = json.load(fp)
        
        if not data or 'tracks' not in data:
            return None
        
        # Convert tracks to DataFrame
        tracks = []
        for track in data.get('tracks', []):
            tracks.append({
                'track_uri': track.get('uri', ''),
                'track_name': track.get('name', ''),
                'artist_name': track.get('artist', {}).get('name', '') if isinstance(track.get('artist'), dict) else '',
                'album_name': track.get('album', {}).get('name', '') if isinstance(track.get('album'), dict) else '',
                'added_at': track.get('addedAt', ''),
            })
        
        if not tracks:
            return None
        
        df = pd.DataFrame(tracks)
        
        # Parse added_at timestamp if available
        if 'added_at' in df.columns:
            df['added_at'] = pd.to_datetime(df['added_at'], errors='coerce')
            df['added_date'] = df['added_at'].dt.date
        
        # Extract track ID from URI
        if 'track_uri' in df.columns:
            df['track_id'] = df['track_uri'].str.replace('spotify:track:', '', regex=False)
        
        return df
    except (json.JSONDecodeError, KeyError, Exception) as e:
        print(f"⚠️  Could not parse YourLibrary.json: {e}")
        return None


def load_playback_errors(technical_log_dir: Path) -> Optional[pd.DataFrame]:
    """Load playback error logs."""
    error_file = technical_log_dir / "PlaybackError.json"
    if not error_file.exists():
        return None
    
    try:
        with open(error_file, 'r', encoding='utf-8') as fp:
            data = json.load(fp)
        
        if not data:
            return None
        
        df = pd.DataFrame(data)
        
        # Parse timestamps
        if 'timestamp_utc' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp_utc'], utc=True, errors='coerce')
            df['date'] = df['timestamp'].dt.date
            df['month'] = df['timestamp'].dt.to_period('M')
        elif 'context_time' in df.columns:
            # Convert milliseconds to datetime
            df['timestamp'] = pd.to_datetime(df['context_time'], unit='ms', utc=True, errors='coerce')
            df['date'] = df['timestamp'].dt.date
            df['month'] = df['timestamp'].dt.to_period('M')
        
        return df
    except (json.JSONDecodeError, Exception) as e:
        print(f"⚠️  Could not parse PlaybackError.json: {e}")
        return None


def load_playback_retries(technical_log_dir: Path) -> Optional[pd.DataFrame]:
    """Load playback retry logs."""
    retry_file = technical_log_dir / "PlaybackRetry.json"
    if not retry_file.exists():
        return None
    
    try:
        with open(retry_file, 'r', encoding='utf-8') as fp:
            data = json.load(fp)
        
        if not data:
            return None
        
        df = pd.DataFrame(data)
        
        # Parse timestamps
        if 'timestamp_utc' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp_utc'], utc=True, errors='coerce')
            df['date'] = df['timestamp'].dt.date
            df['month'] = df['timestamp'].dt.to_period('M')
        elif 'context_time' in df.columns:
            df['timestamp'] = pd.to_datetime(df['context_time'], unit='ms', utc=True, errors='coerce')
            df['date'] = df['timestamp'].dt.date
            df['month'] = df['timestamp'].dt.to_period('M')
        
        return df
    except (json.JSONDecodeError, Exception) as e:
        print(f"⚠️  Could not parse PlaybackRetry.json: {e}")
        return None


def load_webapi_events(technical_log_dir: Path) -> Optional[pd.DataFrame]:
    """Load Web API event logs."""
    webapi_file = technical_log_dir / "WebapiEvent.json"
    if not webapi_file.exists():
        return None
    
    try:
        with open(webapi_file, 'r', encoding='utf-8') as fp:
            data = json.load(fp)
        
        if not data:
            return None
        
        df = pd.DataFrame(data)
        
        # Parse timestamps
        if 'timestamp_utc' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp_utc'], utc=True, errors='coerce')
            df['date'] = df['timestamp'].dt.date
            df['month'] = df['timestamp'].dt.to_period('M')
        elif 'context_time' in df.columns:
            df['timestamp'] = pd.to_datetime(df['context_time'], unit='ms', utc=True, errors='coerce')
            df['date'] = df['timestamp'].dt.date
            df['month'] = df['timestamp'].dt.to_period('M')
        
        return df
    except (json.JSONDecodeError, Exception) as e:
        print(f"⚠️  Could not parse WebapiEvent.json: {e}")
        return None


def consolidate_streaming_history(
    account_data_dir: Path,
    extended_history_dir: Path,
    data_dir: Path
) -> Optional[pd.DataFrame]:
    """Load and consolidate streaming history from both sources.
    
    Returns a unified DataFrame with standardized columns.
    """
    basic_df = load_basic_streaming_history(account_data_dir)
    extended_df = load_extended_streaming_history(extended_history_dir)
    
    # Prefer extended history if available, otherwise use basic
    if extended_df is not None:
        # Use extended history as primary
        df = extended_df.copy()
        
        # Fill in any gaps with basic history if needed
        if basic_df is not None:
            # Only add basic history records that don't overlap with extended
            # This is a simple approach - could be improved with time-based deduplication
            pass
    elif basic_df is not None:
        df = basic_df.copy()
    else:
        return None
    
    # Ensure we have required columns
    required_cols = ['timestamp', 'artist_name', 'track_name', 'minutes_played', 'date', 'month']
    for col in required_cols:
        if col not in df.columns:
            if col == 'track_uri' and 'track_uri' not in df.columns:
                df['track_uri'] = None
            elif col not in df.columns:
                df[col] = None
    
    # Extract track ID from URI if available
    if 'track_uri' in df.columns and df['track_uri'].notna().any():
        df['track_id'] = df['track_uri'].str.replace('spotify:track:', '', regex=False)
    else:
        df['track_id'] = None
    
    # Sort by timestamp
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    return df


def save_dataframe(df: pd.DataFrame, data_dir: Path, filename: str) -> Path:
    """Save DataFrame to parquet file."""
    data_dir.mkdir(parents=True, exist_ok=True)
    output_path = data_dir / filename
    df.to_parquet(output_path, index=False)
    return output_path


def save_json_data(data: Dict[str, Any], data_dir: Path, filename: str) -> Path:
    """Save JSON data to file."""
    data_dir.mkdir(parents=True, exist_ok=True)
    output_path = data_dir / filename
    import json
    with open(output_path, 'w', encoding='utf-8') as fp:
        json.dump(data, fp, indent=2, default=str)
    return output_path


def load_streaming_history(data_dir: Path) -> Optional[pd.DataFrame]:
    """Load streaming history from parquet file."""
    history_path = data_dir / "streaming_history.parquet"
    if not history_path.exists():
        return None
    return pd.read_parquet(history_path)


def load_search_queries_cached(data_dir: Path) -> Optional[pd.DataFrame]:
    """Load search queries from parquet file."""
    path = data_dir / "search_queries.parquet"
    if not path.exists():
        return None
    return pd.read_parquet(path)


def load_wrapped_data_cached(data_dir: Path) -> Optional[Dict[str, Any]]:
    """Load Wrapped data from JSON file."""
    path = data_dir / "wrapped_data.json"
    if not path.exists():
        return None
    with open(path, 'r', encoding='utf-8') as fp:
        return json.load(fp)


def load_follow_data_cached(data_dir: Path) -> Optional[pd.DataFrame]:
    """Load follow data from parquet file."""
    path = data_dir / "follow_data.parquet"
    if not path.exists():
        return None
    return pd.read_parquet(path)


def load_library_snapshot_cached(data_dir: Path) -> Optional[pd.DataFrame]:
    """Load library snapshot from parquet file."""
    path = data_dir / "library_snapshot.parquet"
    if not path.exists():
        return None
    return pd.read_parquet(path)


def load_playback_errors_cached(data_dir: Path) -> Optional[pd.DataFrame]:
    """Load playback errors from parquet file."""
    path = data_dir / "playback_errors.parquet"
    if not path.exists():
        return None
    return pd.read_parquet(path)


def load_playback_retries_cached(data_dir: Path) -> Optional[pd.DataFrame]:
    """Load playback retries from parquet file."""
    path = data_dir / "playback_retries.parquet"
    if not path.exists():
        return None
    return pd.read_parquet(path)


def load_webapi_events_cached(data_dir: Path) -> Optional[pd.DataFrame]:
    """Load Web API events from parquet file."""
    path = data_dir / "webapi_events.parquet"
    if not path.exists():
        return None
    return pd.read_parquet(path)


def sync_all_export_data(
    account_data_dir: Path,
    extended_history_dir: Path,
    technical_log_dir: Path,
    data_dir: Path,
    force: bool = False
) -> Dict[str, Any]:
    """Sync all export data from folders to data catalog.
    
    Args:
        account_data_dir: Path to "Spotify Account Data" folder
        extended_history_dir: Path to "Spotify Extended Streaming History" folder
        technical_log_dir: Path to "Spotify Technical Log Information" folder
        data_dir: Path to data catalog directory
        force: If True, re-sync even if data exists
    
    Returns:
        Dictionary with status of each data type synced
    """
    results = {
        'streaming_history': None,
        'search_queries': None,
        'wrapped_data': None,
        'follow_data': None,
        'library_snapshot': None,
        'playback_errors': None,
        'playback_retries': None,
        'webapi_events': None,
    }
    
    # 1. Streaming History
    if force or not (data_dir / "streaming_history.parquet").exists():
        print("🔄 Syncing streaming history...")
        df = consolidate_streaming_history(account_data_dir, extended_history_dir, data_dir)
        if df is not None and len(df) > 0:
            save_dataframe(df, data_dir, "streaming_history.parquet")
            results['streaming_history'] = len(df)
            print(f"   ✅ Saved {len(df):,} streaming history records")
        else:
            print("   ⚠️  No streaming history found")
    else:
        existing = load_streaming_history(data_dir)
        if existing is not None:
            results['streaming_history'] = len(existing)
            print(f"✅ Streaming history already synced ({len(existing):,} records)")
    
    # 2. Search Queries
    if force or not (data_dir / "search_queries.parquet").exists():
        print("🔄 Syncing search queries...")
        df = load_search_queries(account_data_dir)
        if df is not None and len(df) > 0:
            save_dataframe(df, data_dir, "search_queries.parquet")
            results['search_queries'] = len(df)
            print(f"   ✅ Saved {len(df):,} search queries")
        else:
            print("   ⚠️  No search queries found")
    else:
        existing = load_search_queries_cached(data_dir)
        if existing is not None:
            results['search_queries'] = len(existing)
            print(f"✅ Search queries already synced ({len(existing):,} records)")
    
    # 3. Wrapped Data
    if force or not (data_dir / "wrapped_data.json").exists():
        print("🔄 Syncing Wrapped data...")
        data = load_wrapped_data(account_data_dir)
        if data is not None:
            save_json_data(data, data_dir, "wrapped_data.json")
            results['wrapped_data'] = True
            print("   ✅ Saved Wrapped data")
        else:
            print("   ⚠️  No Wrapped data found")
    else:
        existing = load_wrapped_data_cached(data_dir)
        if existing is not None:
            results['wrapped_data'] = True
            print("✅ Wrapped data already synced")
    
    # 4. Follow Data
    if force or not (data_dir / "follow_data.parquet").exists():
        print("🔄 Syncing follow data...")
        df = load_follow_data(account_data_dir)
        if df is not None and len(df) > 0:
            save_dataframe(df, data_dir, "follow_data.parquet")
            results['follow_data'] = len(df)
            print(f"   ✅ Saved {len(df):,} follow relationships")
        else:
            print("   ⚠️  No follow data found")
    else:
        existing = load_follow_data_cached(data_dir)
        if existing is not None:
            results['follow_data'] = len(existing)
            print(f"✅ Follow data already synced ({len(existing):,} records)")
    
    # 5. Library Snapshot
    if force or not (data_dir / "library_snapshot.parquet").exists():
        print("🔄 Syncing library snapshot...")
        df = load_your_library_snapshot(account_data_dir)
        if df is not None and len(df) > 0:
            save_dataframe(df, data_dir, "library_snapshot.parquet")
            results['library_snapshot'] = len(df)
            print(f"   ✅ Saved {len(df):,} library tracks")
        else:
            print("   ⚠️  No library snapshot found")
    else:
        existing = load_library_snapshot_cached(data_dir)
        if existing is not None:
            results['library_snapshot'] = len(existing)
            print(f"✅ Library snapshot already synced ({len(existing):,} records)")
    
    # 6. Playback Errors
    if force or not (data_dir / "playback_errors.parquet").exists():
        print("🔄 Syncing playback errors...")
        df = load_playback_errors(technical_log_dir)
        if df is not None and len(df) > 0:
            save_dataframe(df, data_dir, "playback_errors.parquet")
            results['playback_errors'] = len(df)
            print(f"   ✅ Saved {len(df):,} playback errors")
        else:
            print("   ⚠️  No playback errors found")
    else:
        existing = load_playback_errors_cached(data_dir)
        if existing is not None:
            results['playback_errors'] = len(existing)
            print(f"✅ Playback errors already synced ({len(existing):,} records)")
    
    # 7. Playback Retries
    if force or not (data_dir / "playback_retries.parquet").exists():
        print("🔄 Syncing playback retries...")
        df = load_playback_retries(technical_log_dir)
        if df is not None and len(df) > 0:
            save_dataframe(df, data_dir, "playback_retries.parquet")
            results['playback_retries'] = len(df)
            print(f"   ✅ Saved {len(df):,} playback retries")
        else:
            print("   ⚠️  No playback retries found")
    else:
        existing = load_playback_retries_cached(data_dir)
        if existing is not None:
            results['playback_retries'] = len(existing)
            print(f"✅ Playback retries already synced ({len(existing):,} records)")
    
    # 8. Web API Events
    if force or not (data_dir / "webapi_events.parquet").exists():
        print("🔄 Syncing Web API events...")
        df = load_webapi_events(technical_log_dir)
        if df is not None and len(df) > 0:
            save_dataframe(df, data_dir, "webapi_events.parquet")
            results['webapi_events'] = len(df)
            print(f"   ✅ Saved {len(df):,} Web API events")
        else:
            print("   ⚠️  No Web API events found")
    else:
        existing = load_webapi_events_cached(data_dir)
        if existing is not None:
            results['webapi_events'] = len(existing)
            print(f"✅ Web API events already synced ({len(existing):,} records)")
    
    return results


# Backward compatibility
def sync_streaming_history(
    account_data_dir: Path,
    extended_history_dir: Path,
    data_dir: Path,
    force: bool = False
) -> Optional[pd.DataFrame]:
    """Sync streaming history from export folders to data catalog.
    
    This is a convenience function that calls sync_all_export_data for just streaming history.
    For full sync, use sync_all_export_data instead.
    """
    results = sync_all_export_data(
        account_data_dir,
        extended_history_dir,
        Path(account_data_dir.parent / "Spotify Technical Log Information"),
        data_dir,
        force=force
    )
    
    if results['streaming_history']:
        return load_streaming_history(data_dir)
    return None
