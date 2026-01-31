#!/usr/bin/env python3
"""
Playlist Health Check Script

Performs comprehensive health checks on your playlist library and provides
recommendations for organization and cleanup.
"""

import argparse
import sys
from pathlib import Path

# Add project root to path (SPOTIM8 directory: automation -> scripts -> src -> project root)
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
import os

# Load environment
env_path = PROJECT_ROOT / ".env"
if env_path.exists():
    load_dotenv(env_path)

import spotipy
from spotipy.oauth2 import SpotifyOAuth

from src.scripts.automation.config import DATA_DIR
from src.scripts.automation.playlist_organization import (
    get_playlist_organization_report,
    print_organization_report,
    find_empty_playlists,
    find_stale_playlists
)
from src.scripts.automation.playlist_aesthetics import check_playlist_health
from src.scripts.automation.error_handling import setup_logging, get_logger, validate_configuration
from src.scripts.common.api_helpers import get_spotify_client, get_user_info


def main():
    parser = argparse.ArgumentParser(
        description="Perform health checks on your Spotify playlist library"
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Attempt to fix issues automatically (use with caution)"
    )
    parser.add_argument(
        "--empty",
        action="store_true",
        help="Check for empty playlists"
    )
    parser.add_argument(
        "--stale",
        action="store_true",
        help="Check for stale playlists (not updated in >1 year)"
    )
    parser.add_argument(
        "--duplicates",
        action="store_true",
        help="Check for duplicate tracks in playlists"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all health checks"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    log_dir = PROJECT_ROOT / "logs"
    logger = setup_logging(log_dir, "INFO" if not args.verbose else "DEBUG")
    
    # Validate configuration
    is_valid, errors = validate_configuration()
    if not is_valid:
        logger.error("Configuration validation failed:")
        for error in errors:
            logger.error(f"  • {error}")
        return 1
    
    # Get Spotify client
    try:
        sp = get_spotify_client(str(__file__))
        user = get_user_info(sp)
        logger.info(f"Authenticated as: {user.get('display_name', 'Unknown')} ({user['id']})")
    except Exception as e:
        logger.error(f"Failed to authenticate: {e}")
        return 1
    
    # Load data
    import pandas as pd
    
    playlists_path = DATA_DIR / "playlists.parquet"
    playlist_tracks_path = DATA_DIR / "playlist_tracks.parquet"
    tracks_path = DATA_DIR / "tracks.parquet"
    
    if not all(p.exists() for p in [playlists_path, playlist_tracks_path, tracks_path]):
        logger.error("Data files not found. Run sync first!")
        return 1
    
    playlists_df = pd.read_parquet(playlists_path)
    playlist_tracks_df = pd.read_parquet(playlist_tracks_path)
    tracks_df = pd.read_parquet(tracks_path)
    
    # Filter to owned playlists only
    owned_playlists = playlists_df[playlists_df.get("is_owned", False) == True].copy()
    
    logger.info(f"Analyzing {len(owned_playlists)} owned playlists...")
    
    # Run checks based on arguments
    run_all = args.all or not any([args.empty, args.stale, args.duplicates])
    
    if run_all or args.empty:
        logger.info("\n" + "="*60)
        logger.info("Checking for empty playlists...")
        empty = find_empty_playlists(owned_playlists, playlist_tracks_df)
        if empty:
            logger.warning(f"Found {len(empty)} empty playlist(s):")
            for pid, name in empty[:20]:  # Limit output
                logger.warning(f"  • {name}")
            if len(empty) > 20:
                logger.warning(f"  ... and {len(empty) - 20} more")
        else:
            logger.info("✅ No empty playlists found")
    
    if run_all or args.stale:
        logger.info("\n" + "="*60)
        logger.info("Checking for stale playlists...")
        stale = find_stale_playlists(owned_playlists, playlist_tracks_df)
        if stale:
            logger.warning(f"Found {len(stale)} stale playlist(s) (>1 year old):")
            for pid, name, days in stale[:20]:
                logger.warning(f"  • {name} ({days} days ago)")
            if len(stale) > 20:
                logger.warning(f"  ... and {len(stale) - 20} more")
        else:
            logger.info("✅ No stale playlists found")
    
    if run_all or args.duplicates:
        logger.info("\n" + "="*60)
        logger.info("Checking for duplicate tracks...")
        from src.scripts.automation.playlist_organization import find_duplicate_tracks_in_playlist
        
        total_duplicates = 0
        playlists_with_dups = []
        for _, playlist in owned_playlists.iterrows():
            dups = find_duplicate_tracks_in_playlist(
                playlist_tracks_df, playlist["playlist_id"]
            )
            if dups:
                total_duplicates += len(dups)
                playlists_with_dups.append((playlist["name"], len(dups)))
        
        if playlists_with_dups:
            logger.warning(f"Found {total_duplicates} duplicate track(s) across {len(playlists_with_dups)} playlist(s):")
            for name, count in sorted(playlists_with_dups, key=lambda x: x[1], reverse=True)[:20]:
                logger.warning(f"  • {name}: {count} duplicate(s)")
            if len(playlists_with_dups) > 20:
                logger.warning(f"  ... and {len(playlists_with_dups) - 20} more playlists")
        else:
            logger.info("✅ No duplicate tracks found")
    
    # Generate organization report
    logger.info("\n" + "="*60)
    logger.info("Generating organization report...")
    report = get_playlist_organization_report(
        owned_playlists, playlist_tracks_df, tracks_df
    )
    print_organization_report(report)
    
    logger.info("\n✅ Health check complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
