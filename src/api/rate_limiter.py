"""Per-API-key rate limiting."""
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional
from fastapi import HTTPException, status
from src.utils.logger import get_logger
from src.models.user import APIKey, RateLimitInfo

logger = get_logger()


class RateLimiter:
    """Per-API-key rate limiter with sliding window."""

    def __init__(self):
        # In-memory storage: {api_key: [(timestamp, count)]}
        self.request_windows: Dict[str, list] = {}

    def check_rate_limit(self, api_key_obj: APIKey) -> RateLimitInfo:
        """
        Check if request is within rate limit.

        Args:
            api_key_obj: APIKey object with rate limit settings

        Returns:
            RateLimitInfo with current limits

        Raises:
            HTTPException if rate limit exceeded
        """
        api_key = api_key_obj.key
        rate_limit = api_key_obj.rate_limit
        rate_period = api_key_obj.rate_period

        current_time = datetime.now(timezone.utc)
        window_start = current_time - timedelta(seconds=rate_period)

        # Initialize window for this key if not exists
        if api_key not in self.request_windows:
            self.request_windows[api_key] = []

        # Clean old requests outside the window
        self.request_windows[api_key] = [
            req_time for req_time in self.request_windows[api_key]
            if req_time > window_start
        ]

        # Count requests in current window
        request_count = len(self.request_windows[api_key])

        # Check if limit exceeded
        if request_count >= rate_limit:
            # Calculate reset time
            oldest_request = min(self.request_windows[api_key])
            reset_time = oldest_request + timedelta(seconds=rate_period)

            logger.warning(
                f"Rate limit exceeded for API key {api_key[:10]}... "
                f"({request_count}/{rate_limit})"
            )

            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Limit: {rate_limit} requests per {rate_period} seconds. "
                       f"Reset at: {reset_time.isoformat()}",
                headers={
                    "X-RateLimit-Limit": str(rate_limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": reset_time.isoformat()
                }
            )

        # Add current request to window
        self.request_windows[api_key].append(current_time)

        # Calculate remaining requests and reset time
        remaining = rate_limit - (request_count + 1)
        reset_time = current_time + timedelta(seconds=rate_period)

        return RateLimitInfo(
            remaining=remaining,
            limit=rate_limit,
            reset_time=reset_time
        )

    def cleanup_old_windows(self):
        """Cleanup old request windows to prevent memory leaks."""
        current_time = datetime.now(timezone.utc)

        # Remove keys with no recent requests (older than 1 hour)
        cleanup_threshold = current_time - timedelta(hours=1)
        
        # Remove entries with no timestamps
        for api_key in list(self.request_windows.keys()):
            if not self.request_windows[api_key]:
                keys_to_remove.append(api_key)

        keys_to_remove = []
        for api_key, requests in self.request_windows.items():
            if not requests or max(requests) < cleanup_threshold:
                keys_to_remove.append(api_key)

        for key in keys_to_remove:
            del self.request_windows[key]

        if keys_to_remove:
            logger.debug(f"Cleaned up {len(keys_to_remove)} old rate limit windows")


# Global rate limiter instance
rate_limiter = RateLimiter()
