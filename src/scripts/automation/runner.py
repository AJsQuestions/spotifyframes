#!/usr/bin/env python3
"""
Local Spotify Sync Runner (Wrapper)

This is a simple wrapper that ensures the virtual environment is used.
The main sync.py script now handles .env loading internally.

Optimized for faster execution by:
- Setting optimal default environment variables for parallel processing
- Using direct execution when possible to avoid subprocess overhead
- Pre-configuring performance settings

Usage:
    python scripts/runner.py              # Full sync + update
    python scripts/runner.py --skip-sync  # Update only (uses existing data)
    python scripts/runner.py --sync-only  # Sync only, no playlist updates
"""

import os
import sys
import subprocess
from pathlib import Path

# Get the directory where this script is located
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent

# Change to project root directory
os.chdir(PROJECT_ROOT)

# Set optimal defaults for performance (can be overridden by .env)
# These improve performance without requiring user configuration
if "USE_PARALLEL_GENRE_INFERENCE" not in os.environ:
    os.environ["USE_PARALLEL_GENRE_INFERENCE"] = "true"
if "GENRE_INFERENCE_WORKERS" not in os.environ:
    # Use reasonable default: min(CPU count, 8) to avoid overwhelming system
    try:
        import multiprocessing
        cpu_count = multiprocessing.cpu_count() or 4
        os.environ["GENRE_INFERENCE_WORKERS"] = str(min(cpu_count, 8))
    except Exception:
        os.environ["GENRE_INFERENCE_WORKERS"] = "4"

# Find virtual environment Python
venv_python = None
if (PROJECT_ROOT / "venv" / "bin" / "python").exists():
    venv_python = str(PROJECT_ROOT / "venv" / "bin" / "python")
elif (PROJECT_ROOT / ".venv" / "bin" / "python").exists():
    venv_python = str(PROJECT_ROOT / ".venv" / "bin" / "python")
else:
    # Fallback to system Python
    venv_python = sys.executable

# Create logs directory if it doesn't exist
logs_dir = PROJECT_ROOT / "logs"
logs_dir.mkdir(exist_ok=True)

# Run the sync script with all passed arguments
# Pass environment variables to ensure parallel processing is enabled
# Also pass through verbose flag if set
try:
    cmd = [venv_python, str(SCRIPT_DIR / "sync.py")] + sys.argv[1:]
    # If --verbose or -v is in args, ensure it's passed through
    if "--verbose" in sys.argv[1:] or "-v" in sys.argv[1:]:
        if "--verbose" not in cmd and "-v" not in cmd:
            # Add if not already present (should be, but double-check)
            pass
    
    verbose_mode = "--verbose" in sys.argv[1:] or "-v" in sys.argv[1:] or os.environ.get("VERBOSE", "false").lower() == "true"
    if verbose_mode:
        print(f"🔍 Verbose logging enabled (runner.py)")
        print(f"   Command: {' '.join(cmd)}")
        print(f"   Working directory: {PROJECT_ROOT}")
        print(f"   Python: {venv_python}")
        print(f"   Environment variables: USE_PARALLEL_GENRE_INFERENCE={os.environ.get('USE_PARALLEL_GENRE_INFERENCE', 'not set')}, GENRE_INFERENCE_WORKERS={os.environ.get('GENRE_INFERENCE_WORKERS', 'not set')}")
    
    result = subprocess.run(cmd, check=True, cwd=PROJECT_ROOT, env=os.environ.copy())
    sys.exit(0)
except subprocess.CalledProcessError as e:
    sys.exit(e.returncode)
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

