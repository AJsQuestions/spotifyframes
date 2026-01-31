"""
Project path utilities: single source of truth for project root and data directory.

Use these everywhere so the data folder is always under the SPOTIM8 project directory,
unless SPOTIM8_DATA_DIR or DATA_DIR env is set.
"""

import os
from pathlib import Path

# Markers that identify the project root (SPOTIM8 directory)
_PROJECT_MARKERS = ("pyproject.toml", ".git")


def get_project_root(current_file: str = None) -> Path:
    """
    Get the project root directory (the SPOTIM8 directory containing pyproject.toml).

    Prefer walking up and looking for pyproject.toml or .git so the result is correct
    regardless of where the calling file lives.

    Args:
        current_file: Path to the current file (use __file__). If None, use cwd.

    Returns:
        Path to project root (directory containing pyproject.toml).
    """
    if current_file is not None:
        path = Path(current_file).resolve()
        if path.is_file():
            path = path.parent
    else:
        path = Path.cwd()

    for _ in range(8):  # Max depth to avoid infinite loop
        if path is None or not path:
            break
        for marker in _PROJECT_MARKERS:
            if (path / marker).exists():
                return path.resolve()
        path = path.parent if path != path.parent else None

    # Fallback: assume we're under src/ so project root is parent of src
    start = Path(current_file).resolve() if current_file else Path.cwd().resolve()
    start = start if start.is_dir() else start.parent
    parts = start.parts
    try:
        src_index = parts.index("src")
        return Path(*parts[:src_index]).resolve()
    except (ValueError, IndexError):
        pass
    return Path.cwd().resolve()


def get_data_dir(current_file: str = None) -> Path:
    """
    Get the data directory. Always under project root unless env overrides.

    Uses SPOTIM8_DATA_DIR or DATA_DIR env if set; otherwise returns
    (project root) / "data" so data lives inside SPOTIM8, not in a parent "Project" folder.

    Args:
        current_file: Path to the current file (use __file__). If None, use cwd for project root.

    Returns:
        Path to data directory (resolved).
    """
    root = get_project_root(current_file)
    env_path = os.environ.get("SPOTIM8_DATA_DIR") or os.environ.get("DATA_DIR")
    if env_path:
        return Path(env_path).resolve()
    return (root / "data").resolve()
