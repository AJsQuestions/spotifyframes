"""
Rate limiting utilities for Spotify API calls.

Provides exponential backoff, retry logic, and response caching to handle 429 rate limit errors.
"""

from __future__ import annotations

import time
import random
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, TypeVar, Optional

from spotipy.exceptions import SpotifyException

# Configuration
DEFAULT_REQUEST_DELAY = 0.3  # 300ms between requests (balanced)
RATE_LIMIT_BACKOFF_BASE = 3  # Exponential backoff multiplier
MAX_RETRIES = 5  # Maximum retry attempts
MAX_WAIT_TIME = 300  # Cap wait time at 5 minutes

# Response cache settings
RESPONSE_CACHE_DIR: Optional[Path] = None  # Set to enable API response caching
RESPONSE_CACHE_TTL = 3600  # Cache TTL in seconds (1 hour default)

T = TypeVar("T")


def set_response_cache(cache_dir: Path, ttl: int = 3600) -> None:
    """Enable API response caching to reduce rate limit hits."""
    global RESPONSE_CACHE_DIR, RESPONSE_CACHE_TTL
    RESPONSE_CACHE_DIR = cache_dir
    RESPONSE_CACHE_TTL = ttl
    cache_dir.mkdir(parents=True, exist_ok=True)
    print(f"📦 API response cache enabled: {cache_dir} (TTL: {ttl}s)")


def _cache_key(func_name: str, args: tuple, kwargs: dict) -> str:
    """Generate cache key from function call signature."""
    key_data = json.dumps([func_name, str(args), sorted(kwargs.items())], sort_keys=True)
    return hashlib.md5(key_data.encode()).hexdigest()[:16]


def _get_cached_response(cache_key: str) -> Optional[Any]:
    """Get cached response if valid."""
    if not RESPONSE_CACHE_DIR:
        return None
    cache_file = RESPONSE_CACHE_DIR / f"{cache_key}.json"
    if not cache_file.exists():
        return None
    try:
        data = json.loads(cache_file.read_text())
        if time.time() - data.get("timestamp", 0) < RESPONSE_CACHE_TTL:
            return data.get("response")
    except Exception:
        pass
    return None


def _save_cached_response(cache_key: str, response: Any) -> None:
    """Save response to cache."""
    if not RESPONSE_CACHE_DIR:
        return
    try:
        cache_file = RESPONSE_CACHE_DIR / f"{cache_key}.json"
        data = {"timestamp": time.time(), "response": response}
        cache_file.write_text(json.dumps(data))
    except Exception:
        pass  # Ignore cache write errors


class RateLimitError(Exception):
    """Raised when max retries exceeded for rate-limited API call."""
    pass


def rate_limited_call(
    func: Callable[..., T],
    *args: Any,
    delay: float = DEFAULT_REQUEST_DELAY,
    max_retries: int = MAX_RETRIES,
    verbose: bool = True,
    use_cache: bool = True,
    **kwargs: Any,
) -> T:
    """
    Execute a function with rate limiting, caching, and exponential backoff on 429 errors.
    
    Args:
        func: The function to call
        *args: Positional arguments to pass to func
        delay: Pre-request delay in seconds
        max_retries: Maximum number of retry attempts
        verbose: Whether to print retry messages
        use_cache: Whether to use response caching (default True)
        **kwargs: Keyword arguments to pass to func
        
    Returns:
        The result of func(*args, **kwargs)
        
    Raises:
        RateLimitError: If max retries exceeded
        SpotifyException: If a non-429 Spotify error occurs
    """
    # Check cache first
    if use_cache and RESPONSE_CACHE_DIR:
        cache_key = _cache_key(func.__name__, args, kwargs)
        cached = _get_cached_response(cache_key)
        if cached is not None:
            return cached
    
    for attempt in range(max_retries):
        try:
            time.sleep(delay)
            result = func(*args, **kwargs)
            
            # Cache successful response
            if use_cache and RESPONSE_CACHE_DIR:
                _save_cached_response(cache_key, result)
            
            return result
        except SpotifyException as e:
            if e.http_status == 429:
                wait_time = _calculate_wait_time(e, attempt)
                if verbose:
                    print(f"⏳ Rate limited. Waiting {wait_time:.0f}s before retry ({attempt + 1}/{max_retries})...")
                time.sleep(wait_time)
            else:
                raise
    
    raise RateLimitError(f"Max retries ({max_retries}) exceeded for API call")


def _calculate_wait_time(error: SpotifyException, attempt: int) -> float:
    """Calculate wait time based on Retry-After header or exponential backoff."""
    retry_after = 0
    if hasattr(error, 'headers') and error.headers:
        retry_after = int(error.headers.get('Retry-After', 0))
    
    if retry_after > 0:
        wait_time = retry_after + random.uniform(1, 5)
    else:
        wait_time = (RATE_LIMIT_BACKOFF_BASE ** attempt) + random.uniform(0, 1)
    
    return min(wait_time, MAX_WAIT_TIME)


