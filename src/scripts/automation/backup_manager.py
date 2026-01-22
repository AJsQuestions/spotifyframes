#!/usr/bin/env python3
"""
Backup Management Script

Manage playlist backups created by data protection features.
"""

import argparse
import json
from pathlib import Path
from datetime import datetime
from typing import List, Optional

from .sync import DATA_DIR

BACKUP_DIR = DATA_DIR / ".backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def list_backups(playlist_id: Optional[str] = None, limit: int = 20) -> List[Path]:
    """List available backups."""
    backups = sorted(BACKUP_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    
    if playlist_id:
        backups = [b for b in backups if playlist_id[:8] in b.name]
    
    return backups[:limit]


def show_backup_info(backup_file: Path) -> None:
    """Show information about a backup."""
    try:
        with open(backup_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"\n📦 Backup: {backup_file.name}")
        print(f"   Playlist: {data.get('playlist_name', 'Unknown')}")
        print(f"   Playlist ID: {data.get('playlist_id', 'Unknown')}")
        print(f"   Tracks: {data.get('track_count', 0)}")
        print(f"   Created: {data.get('backup_timestamp', 'Unknown')}")
        print(f"   Reason: {data.get('backup_reason', 'Unknown')}")
    except Exception as e:
        print(f"❌ Error reading backup: {e}")


def main():
    parser = argparse.ArgumentParser(description="Manage playlist backups")
    parser.add_argument("--list", action="store_true", help="List all backups")
    parser.add_argument("--playlist-id", help="Filter by playlist ID")
    parser.add_argument("--info", help="Show info for specific backup file")
    parser.add_argument("--cleanup", type=int, metavar="DAYS", help="Delete backups older than N days")
    
    args = parser.parse_args()
    
    if args.info:
        show_backup_info(Path(args.info))
    elif args.cleanup:
        from .data_protection import cleanup_old_backups
        deleted = cleanup_old_backups(keep_days=args.cleanup)
        print(f"✅ Cleaned up {deleted} backup(s)")
    else:
        # List backups
        backups = list_backups(args.playlist_id)
        if backups:
            print(f"📦 Found {len(backups)} backup(s):\n")
            for backup in backups:
                show_backup_info(backup)
        else:
            print("No backups found")


if __name__ == "__main__":
    main()
