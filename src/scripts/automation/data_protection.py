"""
Data Protection & Safety Module

Provides safeguards to prevent data loss during playlist operations.
Includes backup, validation, and recovery mechanisms.
"""

import spotipy
import pandas as pd
import json
from typing import Dict, List, Set, Optional, Tuple
from datetime import datetime
from pathlib import Path
import shutil

from .sync import DATA_DIR, api_call, log, verbose_log, get_playlist_tracks


BACKUP_DIR = DATA_DIR / ".backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def create_playlist_backup(
    sp: spotipy.Spotify,
    playlist_id: str,
    playlist_name: str
) -> Optional[Path]:
    """
    Create a backup of a playlist before destructive operations.
    
    Args:
        sp: Spotify client
        playlist_id: Playlist ID to backup
        playlist_name: Playlist name (for backup filename)
    
    Returns:
        Path to backup file, or None if backup failed
    """
    try:
        # Get all tracks
        tracks = get_playlist_tracks(sp, playlist_id, force_refresh=True)
        
        # Get playlist metadata
        pl = api_call(sp.playlist, playlist_id, fields="name,description,public,collaborative")
        
        # Create backup data
        backup_data = {
            "playlist_id": playlist_id,
            "playlist_name": playlist_name or pl.get("name", "Unknown"),
            "description": pl.get("description", ""),
            "public": pl.get("public", False),
            "collaborative": pl.get("collaborative", False),
            "tracks": list(tracks),
            "track_count": len(tracks),
            "backup_timestamp": datetime.now().isoformat(),
            "backup_reason": "pre_destructive_operation"
        }
        
        # Save backup
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(c for c in playlist_name if c.isalnum() or c in (' ', '-', '_')).strip()[:50]
        backup_file = BACKUP_DIR / f"{safe_name}_{playlist_id[:8]}_{timestamp}.json"
        
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, indent=2, ensure_ascii=False)
        
        verbose_log(f"  💾 Created backup: {backup_file.name} ({len(tracks)} tracks)")
        return backup_file
        
    except Exception as e:
        log(f"  ⚠️  Failed to create backup for {playlist_name}: {e}")
        return None


def restore_playlist_from_backup(
    sp: spotipy.Spotify,
    backup_file: Path,
    target_playlist_id: Optional[str] = None,
    dry_run: bool = True
) -> bool:
    """
    Restore a playlist from backup.
    
    Args:
        sp: Spotify client
        backup_file: Path to backup JSON file
        target_playlist_id: Optional playlist ID to restore to (creates new if None)
        dry_run: If True, only show what would be restored
    
    Returns:
        True if successful, False otherwise
    """
    try:
        with open(backup_file, 'r', encoding='utf-8') as f:
            backup_data = json.load(f)
        
        tracks = backup_data.get("tracks", [])
        playlist_name = backup_data.get("playlist_name", "Restored Playlist")
        
        if dry_run:
            log(f"  [DRY RUN] Would restore '{playlist_name}' with {len(tracks)} tracks")
            return True
        
        user = api_call(sp.me)
        user_id = user["id"]
        
        if target_playlist_id:
            # Restore to existing playlist
            pid = target_playlist_id
            # Clear existing tracks first
            current_tracks = get_playlist_tracks(sp, pid)
            if current_tracks:
                api_call(sp.playlist_remove_all_occurrences_of_items, pid, list(current_tracks))
        else:
            # Create new playlist
            pl = api_call(
                sp.user_playlist_create,
                user_id,
                playlist_name,
                public=backup_data.get("public", False),
                collaborative=backup_data.get("collaborative", False),
                description=backup_data.get("description", "")
            )
            pid = pl["id"]
        
        # Add tracks
        from .sync import _chunked
        for chunk in _chunked(tracks, 50):
            api_call(sp.playlist_add_items, pid, chunk)
        
        log(f"  ✅ Restored '{playlist_name}' with {len(tracks)} tracks")
        return True
        
    except Exception as e:
        log(f"  ❌ Failed to restore from backup: {e}")
        return False


def validate_track_preservation(
    before_tracks: Set[str],
    after_tracks: Set[str],
    expected_additions: Optional[Set[str]] = None,
    expected_removals: Optional[Set[str]] = None
) -> Tuple[bool, List[str]]:
    """
    Validate that tracks are preserved correctly after an operation.
    
    Args:
        before_tracks: Set of track URIs before operation
        after_tracks: Set of track URIs after operation
        expected_additions: Optional set of tracks expected to be added
        expected_removals: Optional set of tracks expected to be removed
    
    Returns:
        Tuple of (is_valid, list_of_issues)
    """
    issues = []
    
    # Check for unexpected removals
    unexpected_removals = before_tracks - after_tracks
    if expected_removals:
        unexpected_removals = unexpected_removals - expected_removals
    
    if unexpected_removals:
        issues.append(f"Unexpected track removals: {len(unexpected_removals)} tracks")
        verbose_log(f"  ⚠️  Unexpected removals: {list(unexpected_removals)[:10]}")
    
    # Check for expected additions
    if expected_additions:
        missing_additions = expected_additions - after_tracks
        if missing_additions:
            issues.append(f"Missing expected additions: {len(missing_additions)} tracks")
    
    # Check total count (should increase or stay same, not decrease unexpectedly)
    if not expected_removals and len(after_tracks) < len(before_tracks):
        issues.append(f"Track count decreased unexpectedly: {len(before_tracks)} -> {len(after_tracks)}")
    
    return len(issues) == 0, issues


def safe_remove_tracks_from_playlist(
    sp: spotipy.Spotify,
    playlist_id: str,
    playlist_name: str,
    tracks_to_remove: List[str],
    create_backup: bool = True,
    validate_after: bool = True
) -> Tuple[bool, Optional[Path]]:
    """
    Safely remove tracks from a playlist with backup and validation.
    
    Args:
        sp: Spotify client
        playlist_id: Playlist ID
        playlist_name: Playlist name (for logging/backup)
        tracks_to_remove: List of track URIs to remove
        create_backup: If True, create backup before removal
        validate_after: If True, validate tracks after removal
    
    Returns:
        Tuple of (success, backup_file_path)
    """
    backup_file = None
    
    try:
        # Get tracks before removal
        before_tracks = get_playlist_tracks(sp, playlist_id, force_refresh=True)
        
        # Create backup if requested
        if create_backup and tracks_to_remove:
            backup_file = create_playlist_backup(sp, playlist_id, playlist_name)
        
        # Remove tracks
        if tracks_to_remove:
            from .sync import _chunked
            for chunk in _chunked(tracks_to_remove, 50):
                api_call(sp.playlist_remove_all_occurrences_of_items, playlist_id, chunk)
            
            # Invalidate cache
            from .sync import _playlist_tracks_cache
            if playlist_id in _playlist_tracks_cache:
                del _playlist_tracks_cache[playlist_id]
        
        # Validate after removal
        if validate_after:
            after_tracks = get_playlist_tracks(sp, playlist_id, force_refresh=True)
            is_valid, issues = validate_track_preservation(
                before_tracks,
                after_tracks,
                expected_removals=set(tracks_to_remove)
            )
            
            if not is_valid:
                log(f"  ⚠️  Validation issues after removal: {', '.join(issues)}")
                if backup_file:
                    log(f"  💾 Backup available at: {backup_file}")
                return False, backup_file
        
        return True, backup_file
        
    except Exception as e:
        log(f"  ❌ Error during safe track removal: {e}")
        if backup_file:
            log(f"  💾 Backup available at: {backup_file}")
        return False, backup_file


def safe_delete_playlist(
    sp: spotipy.Spotify,
    playlist_id: str,
    playlist_name: str,
    create_backup: bool = True,
    verify_tracks_preserved_in: Optional[str] = None
) -> Tuple[bool, Optional[Path]]:
    """
    Safely delete a playlist with backup and verification.
    
    Args:
        sp: Spotify client
        playlist_id: Playlist ID to delete
        playlist_name: Playlist name (for logging/backup)
        create_backup: If True, create backup before deletion
        verify_tracks_preserved_in: Optional playlist ID to verify tracks are preserved there
    
    Returns:
        Tuple of (success, backup_file_path)
    """
    backup_file = None
    
    try:
        # Get tracks before deletion
        tracks_before = get_playlist_tracks(sp, playlist_id, force_refresh=True)
        
        # Create backup if requested
        if create_backup:
            backup_file = create_playlist_backup(sp, playlist_id, playlist_name)
        
        # Verify tracks are preserved in another playlist if specified
        if verify_tracks_preserved_in:
            preserved_tracks = get_playlist_tracks(sp, verify_tracks_preserved_in, force_refresh=True)
            missing_tracks = tracks_before - preserved_tracks
            if missing_tracks:
                log(f"  ⚠️  WARNING: {len(missing_tracks)} tracks from '{playlist_name}' are NOT in target playlist!")
                log(f"  💾 Backup created before deletion: {backup_file.name if backup_file else 'Failed'}")
                # Don't delete if tracks aren't preserved
                return False, backup_file
        
        # Delete playlist
        user = api_call(sp.me)
        user_id = user["id"]
        api_call(sp.user_playlist_unfollow, user_id, playlist_id)
        
        log(f"  ✅ Deleted playlist '{playlist_name}' (backup: {backup_file.name if backup_file else 'None'})")
        return True, backup_file
        
    except Exception as e:
        log(f"  ❌ Error during safe playlist deletion: {e}")
        if backup_file:
            log(f"  💾 Backup available at: {backup_file}")
        return False, backup_file


def list_backups(playlist_id: Optional[str] = None) -> List[Path]:
    """
    List available backups.
    
    Args:
        playlist_id: Optional playlist ID to filter backups
    
    Returns:
        List of backup file paths
    """
    backups = sorted(BACKUP_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    
    if playlist_id:
        # Filter by playlist ID
        backups = [b for b in backups if playlist_id[:8] in b.name]
    
    return backups


def cleanup_old_backups(keep_days: int = 30) -> int:
    """
    Clean up old backup files.
    
    Args:
        keep_days: Number of days to keep backups
    
    Returns:
        Number of backups deleted
    """
    cutoff = datetime.now().timestamp() - (keep_days * 24 * 60 * 60)
    deleted = 0
    
    for backup_file in BACKUP_DIR.glob("*.json"):
        if backup_file.stat().st_mtime < cutoff:
            try:
                backup_file.unlink()
                deleted += 1
            except Exception as e:
                verbose_log(f"  Failed to delete old backup {backup_file.name}: {e}")
    
    if deleted > 0:
        log(f"  🗑️  Cleaned up {deleted} old backup(s) (older than {keep_days} days)")
    
    return deleted
