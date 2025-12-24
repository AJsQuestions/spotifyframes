#!/usr/bin/env python3
"""
Local Spotify Sync Runner

This script runs the spotify_sync.py script locally with proper environment setup.
It's designed to be run manually or via cron for scheduled automation.

Usage:
    python scripts/run_sync_local.py              # Full sync + update
    python scripts/run_sync_local.py --skip-sync  # Update only (uses existing data)
    python scripts/run_sync_local.py --sync-only  # Sync only, no playlist updates
"""

import os
import sys
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# Get the directory where this script is located
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

# Change to project root directory
os.chdir(PROJECT_ROOT)

# Activate virtual environment if it exists
venv_python = None
if (PROJECT_ROOT / "venv" / "bin" / "python").exists():
    venv_python = str(PROJECT_ROOT / "venv" / "bin" / "python")
elif (PROJECT_ROOT / ".venv" / "bin" / "python").exists():
    venv_python = str(PROJECT_ROOT / ".venv" / "bin" / "python")
else:
    print("ERROR: Virtual environment not found!")
    print("Run python scripts/setup_local.py first to set up the environment")
    sys.exit(1)

# Load environment variables from .env file if it exists
env_path = PROJECT_ROOT / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"✅ Loaded credentials from {env_path}")
else:
    print(f"⚠️  No .env file found at {env_path}")
    print("   Using environment variables if set")

# Check for required environment variables
if not os.environ.get("SPOTIPY_CLIENT_ID") or not os.environ.get("SPOTIPY_CLIENT_SECRET"):
    print("ERROR: SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET must be set")
    print("Either export them or add them to a .env file in the project root")
    print("See README.md for setup instructions")
    sys.exit(1)

# Create logs directory if it doesn't exist
logs_dir = PROJECT_ROOT / "logs"
logs_dir.mkdir(exist_ok=True)

# Run the sync script with all passed arguments
import datetime
print(f"Starting Spotify sync at {datetime.datetime.now()}")
print("=" * 60)

try:
    # Pass all command-line arguments to the sync script
    cmd = [venv_python, str(SCRIPT_DIR / "spotify_sync.py")] + sys.argv[1:]
    result = subprocess.run(cmd, check=True, cwd=PROJECT_ROOT)
    
    print("=" * 60)
    print(f"Sync completed successfully at {datetime.datetime.now()}")
    sys.exit(0)
except subprocess.CalledProcessError as e:
    print("=" * 60)
    print(f"Sync failed with exit code {e.returncode} at {datetime.datetime.now()}")
    sys.exit(e.returncode)
except Exception as e:
    print("=" * 60)
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

