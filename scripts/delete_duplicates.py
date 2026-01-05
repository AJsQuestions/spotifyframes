#!/usr/bin/env python3
"""Quick script to delete duplicate playlists."""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Load environment variables from .env file if available
try:
    from dotenv import load_dotenv
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass  # dotenv not available, use environment variables directly

# Import after path setup
from scripts.sync import get_spotify_client, delete_duplicate_playlists, log

if __name__ == "__main__":
    log("=" * 60)
    log("Delete Duplicate Playlists")
    log("=" * 60)
    
    try:
        sp = get_spotify_client()
        delete_duplicate_playlists(sp)
        log("\n" + "=" * 60)
        log("✅ Complete!")
        log("=" * 60)
    except Exception as e:
        log(f"ERROR: {e}")
        import traceback
        log(traceback.format_exc())
        sys.exit(1)

