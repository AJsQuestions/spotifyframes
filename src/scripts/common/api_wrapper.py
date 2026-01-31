"""
Standardized API Wrapper

Provides a consistent interface for all Spotify API calls with:
- Automatic retry logic
- Rate limit handling
- Error handling
- Logging
"""

import time
import random
import logging
from typing import Callable, Any, Optional
from functools import wraps
import requests
import spotipy

from src.scripts.automation.config import (
    API_RATE_LIMIT_MAX_RETRIES,
    API_RATE_LIMIT_DELAY,
    API_RATE_LIMIT_BACKOFF_MULTIPLIER,
    API_RATE_LIMIT_INITIAL_DELAY
)
from src.scripts.automation.error_handling import get_logger, RetryableError

logger = get_logger()

# Global adaptive backoff multiplier
_RATE_BACKOFF_MULTIPLIER = API_RATE_LIMIT_BACKOFF_MULTIPLIER
_RATE_BACKOFF_MAX = 16.0


def reset_rate_backoff() -> None:
    """Reset the rate limit backoff multiplier to default."""
    global _RATE_BACKOFF_MULTIPLIER
    _RATE_BACKOFF_MULTIPLIER = API_RATE_LIMIT_BACKOFF_MULTIPLIER


def get_rate_backoff_multiplier() -> float:
    """Get the current rate limit backoff multiplier."""
    return _RATE_BACKOFF_MULTIPLIER


def api_call(
    fn: Callable,
    *args,
    max_retries: int = API_RATE_LIMIT_MAX_RETRIES,
    backoff_factor: float = 1.0,
    verbose: bool = False,
    **kwargs
) -> Any:
    """
    Call Spotify API method with standardized retry and error handling.
    
    This is the primary wrapper for all Spotify API calls. It provides:
    - Automatic retry on rate limits and transient errors
    - Exponential backoff with jitter
    - Adaptive rate limiting
    - Comprehensive error logging
    
    Args:
        fn: Callable (typically a bound method on spotipy.Spotify client)
        *args: Positional arguments to pass to fn
        max_retries: Maximum number of retry attempts
        backoff_factor: Base backoff multiplier
        verbose: Enable verbose logging
        **kwargs: Keyword arguments to pass to fn
    
    Returns:
        Result from the API call
    
    Raises:
        RuntimeError: If all retries are exhausted
        spotipy.SpotifyException: For non-retryable errors
    """
    global _RATE_BACKOFF_MULTIPLIER
    
    fn_name = getattr(fn, '__name__', str(fn))
    
    if verbose:
        logger.debug(f"API call: {fn_name}()")
        if args:
            logger.debug(f"  Args: {args[:2]}{'...' if len(args) > 2 else ''}")
        if kwargs:
            logger.debug(f"  Kwargs: {list(kwargs.keys())}")
    
    for attempt in range(max_retries):
        try:
            result = fn(*args, **kwargs)
            
            # Adaptive delay between successful calls
            base_delay = API_RATE_LIMIT_DELAY
            delay = base_delay * _RATE_BACKOFF_MULTIPLIER
            
            if delay > 0:
                if verbose and delay > 0.2:
                    logger.debug(f"  API delay: {delay:.2f}s (backoff: {_RATE_BACKOFF_MULTIPLIER:.2f})")
                time.sleep(delay)
            
            # Decay multiplier on success
            _RATE_BACKOFF_MULTIPLIER = max(1.0, _RATE_BACKOFF_MULTIPLIER * 0.90)
            
            return result
            
        except Exception as e:
            status = getattr(e, "http_status", None) or getattr(e, "status", None)
            retry_after = _extract_retry_after(e)
            
            is_rate = status == 429 or (retry_after is not None) or ("rate limit" in str(e).lower())
            is_transient = isinstance(e, (
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.ReadTimeout
            ))
            
            if is_rate or is_transient:
                wait = _calculate_backoff(attempt, backoff_factor, retry_after)
                
                logger.warning(
                    f"Transient/rate error: {e} — retrying in {wait:.1f}s "
                    f"(attempt {attempt+1}/{max_retries})"
                )
                
                if verbose:
                    logger.debug(f"  API call {fn_name}() failed with status {status}, retry_after={retry_after}")
                
                time.sleep(wait)
                
                # Increase adaptive multiplier
                old_mult = _RATE_BACKOFF_MULTIPLIER
                _RATE_BACKOFF_MULTIPLIER = min(_RATE_BACKOFF_MAX, _RATE_BACKOFF_MULTIPLIER * 2.0)
                
                if verbose and _RATE_BACKOFF_MULTIPLIER != old_mult:
                    logger.debug(f"  Increased backoff multiplier: {old_mult:.2f} → {_RATE_BACKOFF_MULTIPLIER:.2f}")
                
                continue
            
            # Not a retryable error; re-raise
            raise
    
    # Exhausted retries
    raise RuntimeError(f"API call {fn_name}() failed after {max_retries} attempts")


def _extract_retry_after(e: Exception) -> Optional[int]:
    """Extract Retry-After header from exception."""
    # Try headers attribute
    headers = getattr(e, "headers", None)
    if headers and isinstance(headers, dict):
        retry_after = headers.get("Retry-After") or headers.get("retry-after")
        if retry_after:
            try:
                return int(retry_after)
            except (ValueError, TypeError):
                pass
    
    # Try args for nested headers
    if hasattr(e, "args") and e.args:
        for a in e.args:
            if isinstance(a, dict) and "headers" in a:
                headers = a["headers"]
                if isinstance(headers, dict):
                    retry_after = headers.get("Retry-After") or headers.get("retry-after")
                    if retry_after:
                        try:
                            return int(retry_after)
                        except (ValueError, TypeError):
                            pass
    
    return None


def _calculate_backoff(attempt: int, backoff_factor: float, retry_after: Optional[int]) -> float:
    """Calculate backoff delay with exponential backoff and jitter."""
    wait = backoff_factor * (2 ** attempt) + random.uniform(0, 1)
    
    if retry_after:
        wait = max(wait, float(retry_after))
    
    return wait


def safe_api_call(
    fn: Callable,
    *args,
    default_return: Any = None,
    max_retries: int = API_RATE_LIMIT_MAX_RETRIES,
    **kwargs
) -> Any:
    """
    Safe API call that returns default value on error instead of raising.
    
    Use this for non-critical API calls where failure is acceptable.
    
    Args:
        fn: Callable to execute
        *args: Positional arguments
        default_return: Value to return on error
        max_retries: Maximum retry attempts
        **kwargs: Keyword arguments
    
    Returns:
        API result or default_return on error
    """
    try:
        return api_call(fn, *args, max_retries=max_retries, **kwargs)
    except Exception as e:
        logger.warning(f"Safe API call failed: {e}, returning default")
        return default_return
