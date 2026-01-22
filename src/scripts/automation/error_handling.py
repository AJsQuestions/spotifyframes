"""
Error Handling & Logging Infrastructure

Provides robust error handling, logging, and monitoring for production use.
"""

import logging
import sys
import traceback
from typing import Optional, Callable, Any
from functools import wraps
from datetime import datetime
from pathlib import Path

# Configure logging
_logger = None


def setup_logging(log_dir: Path, log_level: str = "INFO") -> logging.Logger:
    """
    Set up structured logging for the application.
    
    Args:
        log_dir: Directory for log files
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    
    Returns:
        Configured logger instance
    """
    global _logger
    
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Create logger
    logger = logging.getLogger("spotim8")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    # File handler (rotating)
    log_file = log_dir / f"spotim8_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    _logger = logger
    return logger


def get_logger() -> logging.Logger:
    """Get the configured logger instance."""
    global _logger
    if _logger is None:
        _logger = logging.getLogger("spotim8")
        if not _logger.handlers:
            # Default console handler if not configured
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(
                logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
            )
            _logger.addHandler(handler)
            _logger.setLevel(logging.INFO)
    return _logger


def handle_errors(
    reraise: bool = False,
    default_return: Any = None,
    log_error: bool = True
):
    """
    Decorator for robust error handling.
    
    Args:
        reraise: If True, re-raise the exception after logging
        default_return: Value to return on error (if not reraise)
        log_error: If True, log the error
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger = get_logger()
                if log_error:
                    logger.error(
                        f"Error in {func.__name__}: {str(e)}",
                        exc_info=True
                    )
                if reraise:
                    raise
                return default_return
        return wrapper
    return decorator


class RetryableError(Exception):
    """Exception that indicates an operation should be retried."""
    pass


class ConfigurationError(Exception):
    """Exception for configuration-related errors."""
    pass


def retry_on_error(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    Decorator to retry a function on error.
    
    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries (seconds)
        backoff: Multiplier for delay on each retry
        exceptions: Tuple of exceptions to catch and retry
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger = get_logger()
                        logger.warning(
                            f"{func.__name__} failed (attempt {attempt + 1}/{max_retries}): {str(e)}. "
                            f"Retrying in {current_delay:.1f}s..."
                        )
                        import time
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger = get_logger()
                        logger.error(
                            f"{func.__name__} failed after {max_retries} attempts: {str(e)}"
                        )
                        raise
            
            if last_exception:
                raise last_exception
        return wrapper
    return decorator


def validate_configuration() -> tuple[bool, list[str]]:
    """
    Validate configuration and environment setup.
    
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    import os
    errors = []
    
    # Check required environment variables
    required_vars = ["SPOTIPY_CLIENT_ID", "SPOTIPY_CLIENT_SECRET"]
    for var in required_vars:
        if not os.environ.get(var):
            errors.append(f"Missing required environment variable: {var}")
    
    # Check data directory
    from .sync import DATA_DIR
    if not DATA_DIR.exists():
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            errors.append(f"Cannot create data directory: {e}")
    
    # Check write permissions
    try:
        test_file = DATA_DIR / ".test_write"
        test_file.write_text("test")
        test_file.unlink()
    except Exception as e:
        errors.append(f"Data directory not writable: {e}")
    
    return len(errors) == 0, errors
