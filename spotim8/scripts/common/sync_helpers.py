"""
Helper functions for triggering syncs after playlist operations.
"""

import os
import sys
import subprocess
from pathlib import Path


def trigger_incremental_sync(quiet: bool = False) -> bool:
    """
    Trigger an incremental sync after playlist operations.
    
    This function runs an incremental sync (without --force) to update
    local cache files after making playlist changes.
    
    Args:
        quiet: If True, suppress output (useful when called from scripts)
    
    Returns:
        True if sync succeeded, False otherwise
    """
    try:
        # Get project root
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        
        # Find Python executable
        python_exe = sys.executable
        
        # Run sync script as subprocess
        cmd = [python_exe, str(project_root / "spotim8" / "scripts" / "automation" / "sync.py"), "--sync-only"]
        
        if quiet:
            result = subprocess.run(cmd, cwd=project_root, capture_output=True, text=True)
            return result.returncode == 0
        else:
            result = subprocess.run(cmd, cwd=project_root)
            return result.returncode == 0
    except Exception as e:
        if not quiet:
            print(f"⚠️  Sync failed: {e}")
        return False

