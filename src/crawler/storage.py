"""Storage module for saving book data and HTML snapshots."""
import hashlib
import json
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from src.utils.logger import get_logger
from src.utils.config import get_settings
from src.models.book import BookInDB, BookChange

logger = get_logger()


class BookStorage:
    """Handle storage of book data and HTML snapshots."""

    def __init__(self, db):
        self.db = db
        self.settings = get_settings()
        self.html_dir = Path(self.settings.html_snapshot_dir)
        self.html_dir.mkdir(parents=True, exist_ok=True)

    def save_html_snapshot(self, html: str, book_url: str) -> str:
        """
        Save HTML snapshot to filesystem.

        Args:
            html: HTML content
            book_url: Source URL of the book

        Returns:
            Path to saved HTML file
        """
        try:
            # Create a filename based on URL hash
            url_hash = hashlib.md5(book_url.encode()).hexdigest()
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            filename = f"book_{url_hash}_{timestamp}.html"
            filepath = self.html_dir / filename

            # Save HTML content
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html)

            logger.debug(f"Saved HTML snapshot: {filepath}")
            return str(filepath)

        except Exception as e:
            logger.error(f"Error saving HTML snapshot for {book_url}: {e}")
            return ""

    @staticmethod
    def compute_content_hash(book_data: Dict[str, Any]) -> str:
        """
        Compute a hash of book content for change detection.

        Args:
            book_data: Book data dictionary

        Returns:
            SHA256 hash of relevant fields
        """
        # Fields to include in hash (exclude metadata)
        relevant_fields = [
            'name', 'description', 'category',
            'price_including_tax', 'price_excluding_tax',
            'availability', 'number_of_reviews', 'rating'
        ]

        # Create a sorted JSON string of relevant fields
        content_dict = {k: book_data.get(k) for k in relevant_fields if k in book_data}
        content_str = json.dumps(content_dict, sort_keys=True)

        # Compute hash
        return hashlib.sha256(content_str.encode()).hexdigest()

    def save_book(self, book_data: Dict[str, Any], html: str) -> Optional[str]:
        """
        Save or update book in database.

        Args:
            book_data: Parsed book data
            html: Raw HTML content

        Returns:
            Book ID or None if save failed
        """
        try:
            collection = self.db.get_collection('books')

            # Save HTML snapshot
            html_path = self.save_html_snapshot(html, book_data['source_url'])

            # Compute content hash
            content_hash = self.compute_content_hash(book_data)

            # Check if book already exists
            existing_book = collection.find_one({'source_url': book_data['source_url']})

            if existing_book:
                # Check if content changed
                if existing_book.get('content_hash') != content_hash:
                    # Log changes
                    self._log_changes(existing_book, book_data, content_hash)

                    # Update existing book
                    update_data = {
                        **book_data,
                        'content_hash': content_hash,
                        'last_updated': datetime.now(timezone.utc),
                        'html_snapshot_path': html_path
                    }
                    collection.update_one(
                        {'_id': existing_book['_id']},
                        {'$set': update_data}
                    )
                    logger.info(f"Updated book: {book_data['name']}")
                    return str(existing_book['_id'])
                else:
                    logger.debug(f"No changes detected for: {book_data['name']}")
                    return str(existing_book['_id'])
            else:
                # Insert new book
                book_in_db = {
                    **book_data,
                    'crawl_timestamp': datetime.now(timezone.utc),
                    'last_updated': datetime.now(timezone.utc),
                    'status': 'active',
                    'content_hash': content_hash,
                    'html_snapshot_path': html_path
                }
                result = collection.insert_one(book_in_db)

                # Log new book
                self._log_new_book(str(result.inserted_id), book_data)

                logger.info(f"Inserted new book: {book_data['name']}")
                return str(result.inserted_id)

        except Exception as e:
            logger.error(f"Error saving book {book_data.get('name', 'Unknown')}: {e}")
            return None

    def _log_changes(self, old_book: Dict, new_data: Dict, new_hash: str):
        """Log changes between old and new book data."""
        try:
            changes_collection = self.db.get_collection('changes')

            # Fields to track for changes
            tracked_fields = [
                'price_including_tax', 'price_excluding_tax',
                'availability', 'number_of_reviews', 'rating', 'description'
            ]

            changed_fields = {}
            for field in tracked_fields:
                old_value = old_book.get(field)
                new_value = new_data.get(field)
                if old_value != new_value:
                    changed_fields[field] = {
                        'old': old_value,
                        'new': new_value
                    }

            if changed_fields:
                change_log = {
                    'book_id': str(old_book['_id']),
                    'book_name': new_data['name'],
                    'change_type': 'updated',
                    'changed_fields': changed_fields,
                    'timestamp': datetime.now(timezone.utc)
                }
                changes_collection.insert_one(change_log)
                logger.info(f"Logged changes for book: {new_data['name']}")

        except Exception as e:
            logger.error(f"Error logging changes: {e}")

    def _log_new_book(self, book_id: str, book_data: Dict):
        """Log a newly discovered book."""
        try:
            changes_collection = self.db.get_collection('changes')

            change_log = {
                'book_id': book_id,
                'book_name': book_data['name'],
                'change_type': 'new',
                'changed_fields': {},
                'timestamp': datetime.now(timezone.utc)
            }
            changes_collection.insert_one(change_log)
            logger.info(f"Logged new book: {book_data['name']}")

        except Exception as e:
            logger.error(f"Error logging new book: {e}")

    def get_crawl_state(self) -> Dict[str, Any]:
        """Get the current crawler state for resumability."""
        try:
            state_collection = self.db.get_collection('crawler_state')
            state = state_collection.find_one({})
            return state or {
                'last_successful_url': None,
                'last_crawl_time': None,
                'total_books_crawled': 0,
                'status': 'idle',
                'error_message': None
            }
        except Exception as e:
            logger.error(f"Error getting crawl state: {e}")
            return {}

    def update_crawl_state(self, state_data: Dict[str, Any]):
        """Update the crawler state."""
        try:
            state_collection = self.db.get_collection('crawler_state')
            state_collection.update_one(
                {},
                {'$set': state_data},
                upsert=True
            )
            logger.debug("Updated crawl state")
        except Exception as e:
            logger.error(f"Error updating crawl state: {e}")
