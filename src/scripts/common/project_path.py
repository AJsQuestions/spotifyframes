"""Project path utilities for scripts."""

from pathlib import Path


def get_project_root(current_file: str) -> Path:
    """
    Get the project root directory.
    
    Args:
        current_file: Path to the current file (use __file__)
    
    Returns:
        Path to project root
    """
    # Calculate depth: scripts/playlist/file.py -> 4 levels up
    #                   scripts/automation/file.py -> 3 levels up
    #                   scripts/utils/file.py -> 3 levels up
    current_path = Path(current_file).resolve()
    
    # Count how many "src" directories we need to go up
    parts = current_path.parts
    try:
        src_index = parts.index("src")
        # Go up to src, then one more to project root
        return Path(*parts[:src_index + 1]).parent
    except ValueError:
        # Fallback: count parents until we find project root markers
        path = current_path
        for _ in range(6):  # Max reasonable depth
            if (path / "pyproject.toml").exists() or (path / ".git").exists():
                return path
            path = path.parent
        # Last resort: assume 4 levels up from scripts
        return current_path.parent.parent.parent.parent


def get_data_dir(current_file: str) -> Path:
    """
    Get the data directory path.
    
    Args:
        current_file: Path to the current file (use __file__)
    
    Returns:
        Path to data directory
    """
    return get_project_root(current_file) / "data"

