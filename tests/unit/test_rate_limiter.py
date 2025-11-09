"""Unit tests for rate limiter."""
import pytest
from datetime import datetime, timezone
from fastapi import HTTPException
from src.api.rate_limiter import RateLimiter
from src.models.user import APIKey


class TestRateLimiter:
    """Test RateLimiter class."""

    def test_check_rate_limit_within_limit(self):
        """Test rate limiting when within limits."""
        limiter = RateLimiter()

        api_key = APIKey(
            key="test_key_1",
            user_id="user_1",
            name="Test",
            rate_limit=10,
            rate_period=3600
        )

        # Should succeed for requests within limit
        for i in range(10):
            rate_info = limiter.check_rate_limit(api_key)
            assert rate_info.remaining >= 0
            assert rate_info.limit == 10

    def test_check_rate_limit_exceeded(self):
        """Test rate limiting when limit exceeded."""
        limiter = RateLimiter()

        api_key = APIKey(
            key="test_key_2",
            user_id="user_1",
            name="Test",
            rate_limit=5,
            rate_period=3600
        )

        # Make requests up to limit
        for i in range(5):
            limiter.check_rate_limit(api_key)

        # Next request should fail
        with pytest.raises(HTTPException) as exc_info:
            limiter.check_rate_limit(api_key)

        assert exc_info.value.status_code == 429

    def test_rate_limit_different_keys(self):
        """Test that different API keys have separate limits."""
        limiter = RateLimiter()

        api_key1 = APIKey(
            key="test_key_3",
            user_id="user_1",
            name="Test",
            rate_limit=5,
            rate_period=3600
        )

        api_key2 = APIKey(
            key="test_key_4",
            user_id="user_2",
            name="Test",
            rate_limit=5,
            rate_period=3600
        )

        # Use up limit for key 1
        for i in range(5):
            limiter.check_rate_limit(api_key1)

        # Key 1 should be blocked
        with pytest.raises(HTTPException):
            limiter.check_rate_limit(api_key1)

        # Key 2 should still work
        rate_info = limiter.check_rate_limit(api_key2)
        assert rate_info.remaining >= 0

    def test_cleanup_old_windows(self):
        """Test cleanup of old rate limit windows."""
        limiter = RateLimiter()

        # Add some request windows
        api_key = APIKey(
            key="test_key_5",
            user_id="user_1",
            name="Test",
            rate_limit=10,
            rate_period=3600
        )

        limiter.check_rate_limit(api_key)

        # Manually add old timestamps
        from datetime import timedelta
        old_time = datetime.now(timezone.utc) - timedelta(hours=2)
        limiter.request_windows["old_key"] = [old_time]

        # Cleanup
        limiter.cleanup_old_windows()

        # Old key should be removed
        assert "old_key" not in limiter.request_windows

        # Recent key should remain
        assert api_key.key in limiter.request_windows
