"""Unit tests for authentication."""
import pytest
from fastapi.security import HTTPAuthorizationCredentials
from src.api.auth import AuthManager


class TestAuthManager:
    """Test AuthManager class."""

    def test_generate_api_key(self, test_db):
        """Test API key generation."""
        auth_manager = AuthManager()
        auth_manager.db = test_db

        key = auth_manager.generate_api_key()

        assert key.startswith("sk_live_")
        assert len(key) > 20

        # Keys should be unique
        key2 = auth_manager.generate_api_key()
        assert key != key2

    def test_create_user(self, test_db):
        """Test user creation."""
        auth_manager = AuthManager()
        auth_manager.db = test_db

        user_id = auth_manager.create_user("testuser", "test@example.com")

        assert user_id is not None

        # Verify user in database
        users_collection = test_db.get_collection('users')
        user = users_collection.find_one({'username': 'testuser'})

        assert user is not None
        assert user['email'] == "test@example.com"
        assert user['is_active'] is True

    def test_create_api_key(self, test_db):
        """Test API key creation."""
        auth_manager = AuthManager()
        auth_manager.db = test_db

        # Create user first
        user_id = auth_manager.create_user("testuser", "test@example.com")

        # Create API key
        api_key = auth_manager.create_api_key(
            user_id=user_id,
            name="Test Key",
            rate_limit=50,
            rate_period=1800
        )

        assert api_key.key.startswith("sk_live_")
        assert api_key.user_id == user_id
        assert api_key.name == "Test Key"
        assert api_key.rate_limit == 50
        assert api_key.is_active is True

    @pytest.mark.asyncio
    async def test_verify_token_valid(self, test_db):
        """Test verifying a valid Bearer token."""
        auth_manager = AuthManager()
        auth_manager.db = test_db

        # Create user and API key
        user_id = auth_manager.create_user("testuser", "test@example.com")
        created_key = auth_manager.create_api_key(user_id, "Test Key")

        # Create Bearer token credentials
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=created_key.key
        )

        # Verify the token
        verified_key = await auth_manager.verify_token(credentials)

        assert verified_key is not None
        assert verified_key.key == created_key.key
        assert verified_key.user_id == user_id

    @pytest.mark.asyncio
    async def test_verify_token_invalid(self, test_db):
        """Test verifying an invalid Bearer token."""
        from fastapi import HTTPException

        auth_manager = AuthManager()
        auth_manager.db = test_db

        # Create credentials with invalid token
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="sk_live_invalid_key"
        )

        # Try to verify non-existent key
        with pytest.raises(HTTPException) as exc_info:
            await auth_manager.verify_token(credentials)

        assert exc_info.value.status_code == 401
        assert "Invalid authentication token" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_verify_token_missing(self, test_db):
        """Test verifying with missing Bearer token."""
        from fastapi import HTTPException

        auth_manager = AuthManager()
        auth_manager.db = test_db

        # Try to verify without credentials
        with pytest.raises(HTTPException) as exc_info:
            await auth_manager.verify_token(None)

        assert exc_info.value.status_code == 401
        assert "Missing authentication token" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_verify_token_inactive(self, test_db):
        """Test verifying an inactive Bearer token."""
        from fastapi import HTTPException

        auth_manager = AuthManager()
        auth_manager.db = test_db

        # Create user and API key
        user_id = auth_manager.create_user("testuser", "test@example.com")
        api_key = auth_manager.create_api_key(user_id, "Test Key")

        # Deactivate the key
        api_keys_collection = test_db.get_collection('api_keys')
        api_keys_collection.update_one(
            {'key': api_key.key},
            {'$set': {'is_active': False}}
        )

        # Create credentials with inactive token
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=api_key.key
        )

        # Try to verify inactive key
        with pytest.raises(HTTPException) as exc_info:
            await auth_manager.verify_token(credentials)

        assert exc_info.value.status_code == 401
        assert "inactive" in exc_info.value.detail.lower()
