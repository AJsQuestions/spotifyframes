"""
Rate limiting utilities for Spotify API calls.

Provides exponential backoff and retry logic to handle 429 rate limit errors.
"""

from __future__ import annotations

import time
import random
from typing import Any, Callable, TypeVar

from spotipy.exceptions import SpotifyException

# Configuration
DEFAULT_REQUEST_DELAY = 0.5  # 500ms between requests (conservative)
RATE_LIMIT_BACKOFF_BASE = 3  # Exponential backoff multiplier
MAX_RETRIES = 5  # Maximum retry attempts
MAX_WAIT_TIME = 300  # Cap wait time at 5 minutes

T = TypeVar("T")


class RateLimitError(Exception):
    """Raised when max retries exceeded for rate-limited API call."""
    pass


def rate_limited_call(
    func: Callable[..., T],
    *args: Any,
    delay: float = DEFAULT_REQUEST_DELAY,
    max_retries: int = MAX_RETRIES,
    verbose: bool = True,
    **kwargs: Any,
) -> T:
    """
    Execute a function with rate limiting and exponential backoff on 429 errors.
    
    Args:
        func: The function to call
        *args: Positional arguments to pass to func
        delay: Pre-request delay in seconds
        max_retries: Maximum number of retry attempts
        verbose: Whether to print retry messages
        **kwargs: Keyword arguments to pass to func
        
    Returns:
        The result of func(*args, **kwargs)
        
    Raises:
        RateLimitError: If max retries exceeded
        SpotifyException: If a non-429 Spotify error occurs
    """
    for attempt in range(max_retries):
        try:
            time.sleep(delay)
            return func(*args, **kwargs)
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


class RateLimiter:
    """
    A rate limiter that can be used as a method wrapper.
    
    Usage:
        limiter = RateLimiter(delay=0.5)
        result = limiter.call(spotify.current_user_playlists, limit=50)
    """
    
    def __init__(
        self,
        delay: float = DEFAULT_REQUEST_DELAY,
        max_retries: int = MAX_RETRIES,
        verbose: bool = True,
    ):
        self.delay = delay
        self.max_retries = max_retries
        self.verbose = verbose
    
    def call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Execute a rate-limited call."""
        return rate_limited_call(
            func, *args,
            delay=self.delay,
            max_retries=self.max_retries,
            verbose=self.verbose,
            **kwargs
        )
