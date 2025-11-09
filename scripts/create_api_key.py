"""Script to create users and API keys."""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.api.auth import auth_manager
from src.utils.database import get_database
from src.utils.logger import setup_logger

setup_logger()


def create_user_and_key(username: str, email: str, key_name: str, rate_limit: int = 100):
    """
    Create a user and API key.

    Args:
        username: Username
        email: Email address
        key_name: Name for the API key
        rate_limit: Request limit per hour
    """
    try:
        # Connect to database
        db = get_database()
        auth_manager.db = db

        # Create user
        print(f"Creating user: {username}")
        user_id = auth_manager.create_user(username, email)
        print(f"[OK] User created with ID: {user_id}")

        # Create API key
        print(f"Creating API key: {key_name}")
        api_key = auth_manager.create_api_key(
            user_id=user_id,
            name=key_name,
            rate_limit=rate_limit,
            rate_period=3600  # 1 hour
        )

        print("\n" + "=" * 60)
        print("API KEY CREATED SUCCESSFULLY")
        print("=" * 60)
        print(f"Username: {username}")
        print(f"Email: {email}")
        print(f"Key Name: {key_name}")
        print(f"Rate Limit: {rate_limit} requests/hour")
        print(f"\nYour API Key:")
        print(f"  {api_key.key}")
        print("\nKeep this key secure! You'll need it for API requests.")
        print("=" * 60)

        # Disconnect
        db.disconnect()

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Create user and API key")
    parser.add_argument("username", help="Username")
    parser.add_argument("email", help="Email address")
    parser.add_argument("--key-name", default="Default API Key", help="API key name")
    parser.add_argument("--rate-limit", type=int, default=100, help="Requests per hour")

    args = parser.parse_args()

    create_user_and_key(args.username, args.email, args.key_name, args.rate_limit)
