"""Database connection and management."""
from typing import Optional
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.database import Database as MongoDatabase
from .config import get_settings
from .logger import get_logger

logger = get_logger()


class Database:
    """MongoDB database wrapper with connection management."""

    def __init__(self):
        self.settings = get_settings()
        self.client: Optional[MongoClient] = None
        self.db: Optional[MongoDatabase] = None

    def connect(self):
        """Establish database connection."""
        try:
            self.client = MongoClient(
                self.settings.mongodb_url,
                serverSelectionTimeoutMS=5000,
                maxPoolSize=50,
                minPoolSize=10
            )
            # Test connection
            self.client.server_info()
            self.db = self.client[self.settings.mongodb_db]
            logger.info(f"Connected to MongoDB: {self.settings.mongodb_db}")
            self._create_indexes()
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise

    def disconnect(self):
        """Close database connection."""
        if self.client:
            self.client.close()
            logger.info("Disconnected from MongoDB")

    def _create_indexes(self):
        """Create database indexes for efficient querying."""
        if self.db is None:
            return

        # Books collection indexes
        books_collection = self.db.books
        books_collection.create_index([("source_url", ASCENDING)], unique=True)
        books_collection.create_index([("rating", DESCENDING)])
        # Compound index for common queries
        books_collection.create_index([
            ("category", ASCENDING),
            ("price_including_tax", ASCENDING),
            ("rating", DESCENDING)
        ])
        books_collection.create_index([("number_of_reviews", DESCENDING)])
        books_collection.create_index([("content_hash", ASCENDING)])
        books_collection.create_index([("last_updated", DESCENDING)])

        # Changes collection indexes
        changes_collection = self.db.changes
        changes_collection.create_index([("timestamp", DESCENDING)])
        changes_collection.create_index([("book_id", ASCENDING)])
        changes_collection.create_index([("change_type", ASCENDING)])

        # Crawler state collection
        state_collection = self.db.crawler_state
        state_collection.create_index([("status", ASCENDING)])

        # Users collection indexes
        users_collection = self.db.users
        users_collection.create_index([("username", ASCENDING)], unique=True)
        users_collection.create_index([("email", ASCENDING)], unique=True)

        # API Keys collection indexes
        api_keys_collection = self.db.api_keys
        api_keys_collection.create_index([("key", ASCENDING)], unique=True)
        api_keys_collection.create_index([("user_id", ASCENDING)])
        api_keys_collection.create_index([("is_active", ASCENDING)])

        logger.info("Database indexes created successfully")

    def get_collection(self, name: str):
        """Get a collection by name."""
        if self.db is None:
            raise Exception("Database not connected")
        return self.db[name]


# Singleton instance
_database: Optional[Database] = None


def get_database() -> Database:
    """Get or create database instance."""
    global _database
    if _database is None:
        _database = Database()
        _database.connect()
    return _database
