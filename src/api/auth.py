"""API key authentication and management."""
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import HTTPException, Security, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from src.utils.database import get_database
from src.utils.logger import get_logger
from src.models.user import APIKey

logger = get_logger()

# Bearer token security scheme
bearer_scheme = HTTPBearer(auto_error=False)


class AuthManager:
    """Manage API key authentication."""

    def __init__(self):
        self.db = get_database()

    def generate_api_key(self) -> str:
        """Generate a secure API key."""
        return f"sk_live_{secrets.token_urlsafe(32)}"

    def create_api_key(
        self,
        user_id: str,
        name: str,
        rate_limit: int = 100,
        rate_period: int = 3600
    ) -> APIKey:
        """
        Create a new API key for a user.

        Args:
            user_id: User ID
            name: Friendly name for the key
            rate_limit: Requests allowed per period
            rate_period: Period in seconds

        Returns:
            Created APIKey object
        """
        try:
            api_keys_collection = self.db.get_collection('api_keys')

            # Generate unique key
            key = self.generate_api_key()

            # Create API key document
            api_key_data = {
                'key': key,
                'user_id': user_id,
                'name': name,
                'is_active': True,
                'created_at': datetime.now(timezone.utc),
                'last_used': None,
                'request_count': 0,
                'rate_limit': rate_limit,
                'rate_period': rate_period
            }

            result = api_keys_collection.insert_one(api_key_data)
            api_key_data['_id'] = str(result.inserted_id)

            logger.info(f"Created API key '{name}' for user {user_id}")
            return APIKey(**api_key_data)

        except Exception as e:
            logger.error(f"Error creating API key: {e}")
            raise

    async def verify_token(
        self,
        credentials: HTTPAuthorizationCredentials = Security(bearer_scheme)
    ) -> Optional[APIKey]:
        """
        Verify Bearer token and return associated key data.

        Args:
            credentials: Bearer token credentials from Authorization header

        Returns:
            APIKey object if valid

        Raises:
            HTTPException if invalid or missing
        """
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing authentication token. Provide Bearer token in Authorization header.",
                headers={"WWW-Authenticate": "Bearer"}
            )

        token = credentials.credentials

        try:
            api_keys_collection = self.db.get_collection('api_keys')

            # Find API key
            key_doc = api_keys_collection.find_one({'key': token})

            if not key_doc:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authentication token",
                    headers={"WWW-Authenticate": "Bearer"}
                )

            if not key_doc.get('is_active', False):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication token is inactive",
                    headers={"WWW-Authenticate": "Bearer"}
                )

            # Update last used timestamp
            api_keys_collection.update_one(
                {'_id': key_doc['_id']},
                {
                    '$set': {'last_used': datetime.now(timezone.utc)},
                    '$inc': {'request_count': 1}
                }
            )

            # Convert to APIKey model
            key_doc['_id'] = str(key_doc['_id'])
            return APIKey(**key_doc)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error verifying token: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error verifying authentication token"
            )

    def create_user(self, username: str, email: str) -> str:
        """
        Create a new user.

        Args:
            username: Username
            email: Email address

        Returns:
            User ID
        """
        try:
            users_collection = self.db.get_collection('users')

            user_data = {
                'username': username,
                'email': email,
                'is_active': True,
                'created_at': datetime.now(timezone.utc)
            }

            result = users_collection.insert_one(user_data)
            user_id = str(result.inserted_id)

            logger.info(f"Created user: {username}")
            return user_id

        except Exception as e:
            logger.error(f"Error creating user: {e}")
            raise


# Global auth manager instance
auth_manager = AuthManager()
