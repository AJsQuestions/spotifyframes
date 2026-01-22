"""Common setup code for scripts."""

import sys
from pathlib import Path
from typing import Optional

from .project_path import get_project_root


def setup_script_environment(
    current_file: str,
    load_dotenv: bool = True,
    add_to_path: bool = True
) -> Path:
    """
    Set up script environment (paths, dotenv).
    
    Args:
        current_file: Path to current file (use __file__)
        load_dotenv: Whether to load .env file
        add_to_path: Whether to add project root to sys.path
    
    Returns:
        Path to project root
    """
    project_root = get_project_root(current_file)
    
    if add_to_path:
        project_root_str = str(project_root)
        if project_root_str not in sys.path:
            sys.path.insert(0, project_root_str)
    
    if load_dotenv:
        try:
            from dotenv import load_dotenv as _load_dotenv
            env_path = project_root / ".env"
            if env_path.exists():
                _load_dotenv(env_path)
        except ImportError:
            pass  # dotenv not available
    
    return project_root

