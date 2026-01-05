#!/usr/bin/env python3
"""List all genre playlists to identify incorrect ones."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

from scripts.sync import get_spotify_client, get_existing_playlists, log

if __name__ == "__main__":
    sp = get_spotify_client()
    existing = get_existing_playlists(sp, force_refresh=True)
    
    genres = ["HipHop", "Dance", "Other"]
    prefix = "Finds"  # Default prefix
    
    log("Genre playlists found:")
    for name in sorted(existing.keys()):
        for genre in genres:
            if name.startswith(genre):
                log(f"  - {name}")
                break

