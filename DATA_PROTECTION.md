# 🛡️ Data Protection & Safety Features

This document describes the comprehensive data protection mechanisms implemented to prevent song data loss.

## 🔒 Protection Mechanisms

### 1. Automatic Backups

**Before any destructive operation:**
- Playlist deletion → Full backup created
- Track removal → Playlist state backed up
- Merge operations → Source playlists backed up

**Backup Location:** `data/.backups/`

**Backup Format:** JSON files containing:
- Playlist metadata (name, description, settings)
- Complete track list (all track URIs)
- Timestamp and reason for backup

### 2. Verification Before Deletion

**All deletion operations verify:**
- Tracks are preserved in target playlist (for merges)
- No unexpected track loss
- Complete data transfer before source deletion

**Example:**
```python
# Before deleting a playlist during merge:
1. Verify all tracks are in target playlist
2. Create backup of source playlist
3. Only delete if verification passes
4. Log backup location for recovery
```

### 3. Safe Track Removal

**Track removal operations:**
- Create backup before removal
- Validate tracks after removal
- Report any unexpected losses
- Provide backup location for recovery

**Used in:**
- Genre master playlist cleanup (removes non-matching tracks)
- All track removal operations

### 4. Merge Safety

**All merge operations:**
- Verify all source tracks are in target before deletion
- Create backups of source playlists
- Validate final track count matches expected
- Abort deletion if verification fails

**Protected Operations:**
- `merge_playlists()` - Two playlist merge
- `merge_multiple_playlists()` - Multiple playlist merge
- `merge_to_new_playlist()` - Merge to new playlist
- `consolidate_old_monthly_playlists()` - Monthly to yearly consolidation

### 5. Consolidation Safety

**Monthly playlist consolidation:**
- Verify all monthly tracks are in yearly playlist
- Create backup before deleting monthly playlists
- Abort deletion if tracks are missing
- Log backup location for recovery

## 📋 Protected Operations

### ✅ Safe Operations (No Data Loss Risk)

These operations **only add tracks** and never remove:
- `update_monthly_playlists()` - Only adds tracks
- `update_genre_split_playlists()` - Only adds tracks
- `sync_full_library()` - Only syncs data, doesn't modify playlists

### ⚠️ Protected Operations (With Backups)

These operations are protected with backups and verification:
- **Track Removal** (genre master playlists)
  - Backup created before removal
  - Validation after removal
  - Recovery available via backup

- **Playlist Deletion** (consolidation, duplicates)
  - Backup created before deletion
  - Verification that tracks are preserved elsewhere
  - Abort if verification fails

- **Merge Operations**
  - Source playlists backed up
  - Verification before deletion
  - Track count validation

## 🔧 Usage

### Automatic Protection

All destructive operations automatically:
1. Create backups
2. Verify data preservation
3. Log backup locations
4. Abort if verification fails

**No configuration needed** - protection is always enabled.

### Manual Backup Management

List backups:
```bash
python src/scripts/automation/backup_manager.py --list
```

Show backup info:
```bash
python src/scripts/automation/backup_manager.py --info backup_file.json
```

Cleanup old backups:
```bash
python src/scripts/automation/backup_manager.py --cleanup 30  # Keep last 30 days
```

### Restore from Backup

```python
from src.scripts.automation.data_protection import restore_playlist_from_backup
from pathlib import Path

# Restore to existing playlist
restore_playlist_from_backlist(
    sp, 
    Path("data/.backups/playlist_backup.json"),
    target_playlist_id="existing_playlist_id",
    dry_run=False
)

# Or create new playlist
restore_playlist_from_backup(
    sp,
    Path("data/.backups/playlist_backup.json"),
    target_playlist_id=None,  # Creates new
    dry_run=False
)
```

## 📊 Verification Examples

### Merge Verification

```
🔍 Verifying all tracks are preserved before deletion...
   ✅ All tracks verified in target playlist
   💾 Backup created: PlaylistName_abc123_20250122_120000.json
   ✓ Deleted: Source Playlist
```

### Failed Verification

```
🔍 Verifying all tracks are preserved before deletion...
   ⚠️  WARNING: 5 tracks from 'Source Playlist' are NOT in target playlist!
   💾 Creating backup and skipping deletion...
   ❌ Deletion aborted - tracks not verified in target playlist
   💾 Backup created: SourcePlaylist_abc123_20250122_120000.json
```

### Track Removal Verification

```
  Playlist Name: Removing 12 track(s) that don't match genre...
  💾 Created backup: PlaylistName_abc123_20250122_120000.json (234 tracks)
  ✅ Track removal completed successfully
```

## 🚨 Safety Guarantees

### ✅ Zero Data Loss Guarantee

1. **All deletions are verified** - Tracks must be confirmed in target before deletion
2. **Automatic backups** - Every destructive operation creates a backup
3. **Abort on failure** - Operations abort if verification fails
4. **Recovery available** - All backups can be restored

### ⚠️ Important Notes

- **Backups are stored locally** in `data/.backups/`
- **Backups are not automatically cleaned** (use `backup_manager.py --cleanup`)
- **Manual operations** (via Spotify app) are not backed up automatically
- **Backup before major operations** if you want extra safety

## 📁 Backup File Format

```json
{
  "playlist_id": "abc123...",
  "playlist_name": "My Playlist",
  "description": "Playlist description",
  "public": false,
  "collaborative": false,
  "tracks": [
    "spotify:track:track1",
    "spotify:track:track2",
    ...
  ],
  "track_count": 234,
  "backup_timestamp": "2025-01-22T12:00:00",
  "backup_reason": "pre_destructive_operation"
}
```

## 🔍 Monitoring

### Check for Recent Backups

```bash
ls -lt data/.backups/ | head -10
```

### Verify Backup Integrity

```python
from src.scripts.automation.data_protection import list_backups

backups = list_backups()
for backup in backups:
    # Check backup file
    with open(backup) as f:
        data = json.load(f)
        print(f"{data['playlist_name']}: {data['track_count']} tracks")
```

## 🎯 Best Practices

1. **Regular Backups**: Clean up old backups periodically (keep last 30 days)
2. **Verify Before Major Operations**: Run health check before large merges
3. **Monitor Backup Directory**: Check backup count and size
4. **Test Restore**: Periodically test restore from backup to ensure it works

## 📝 Summary

**All destructive operations are protected:**
- ✅ Automatic backups
- ✅ Verification before deletion
- ✅ Abort on failure
- ✅ Recovery available

**Your song data is safe!** 🎵
