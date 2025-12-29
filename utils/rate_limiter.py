"""
Rate limiter for API calls and notifications.

Prevents hitting rate limits on external services like Telegram and Discord.
"""

import asyncio
import time
from collections import deque
from typing import Optional

from config.logging_config import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """
    Token bucket rate limiter for async operations.

    Limits the number of operations within a time period.
    """

    def __init__(self, max_calls: int, period: float, name: str = "RateLimiter"):
        """
        Initialize rate limiter.

        Args:
            max_calls: Maximum number of calls allowed
            period: Time period in seconds
            name: Name for logging purposes
        """
        self.max_calls = max_calls
        self.period = period
        self.name = name
        self.calls: deque = deque()
        self._lock = asyncio.Lock()

        logger.info(
            f"{name} initialized: {max_calls} calls per {period}s "
            f"({max_calls / period:.2f} calls/sec)"
        )

    async def acquire(self) -> None:
        """
        Acquire permission to make a call.

        Blocks if rate limit would be exceeded.
        """
        async with self._lock:
            now = time.time()

            # Remove old calls outside the time window
            while self.calls and self.calls[0] < now - self.period:
                self.calls.popleft()

            # Check if we're at the limit
            if len(self.calls) >= self.max_calls:
                # Calculate how long to wait
                oldest_call = self.calls[0]
                sleep_time = self.period - (now - oldest_call)

                if sleep_time > 0:
                    logger.debug(
                        f"{self.name}: Rate limit reached, waiting {sleep_time:.2f}s"
                    )
                    await asyncio.sleep(sleep_time)

                    # Remove expired calls after sleeping
                    now = time.time()
                    while self.calls and self.calls[0] < now - self.period:
                        self.calls.popleft()

            # Record this call
            self.calls.append(time.time())

    async def __aenter__(self):
        """Context manager entry."""
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        pass

    def get_stats(self) -> dict:
        """
        Get current rate limiter statistics.

        Returns:
            Dict with calls_in_window and calls_remaining
        """
        now = time.time()

        # Clean up old calls
        while self.calls and self.calls[0] < now - self.period:
            self.calls.popleft()

        return {
            'calls_in_window': len(self.calls),
            'calls_remaining': max(0, self.max_calls - len(self.calls)),
            'period': self.period,
            'max_calls': self.max_calls
        }


class MultiRateLimiter:
    """
    Multiple rate limiters for tiered limits.

    Example: Telegram allows 30 messages/second AND 20 messages/minute to same chat.
    """

    def __init__(self, limiters: list[RateLimiter], name: str = "MultiRateLimiter"):
        """
        Initialize multi-rate limiter.

        Args:
            limiters: List of RateLimiter instances
            name: Name for logging
        """
        self.limiters = limiters
        self.name = name

        logger.info(f"{name} initialized with {len(limiters)} limiters")

    async def acquire(self) -> None:
        """Acquire permission from all limiters."""
        for limiter in self.limiters:
            await limiter.acquire()

    async def __aenter__(self):
        """Context manager entry."""
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        pass
