"""Unit tests for book storage."""
import pytest
from pathlib import Path
from src.crawler.storage import BookStorage


class TestBookStorage:
    """Test BookStorage class."""

    def test_compute_content_hash(self, sample_book_data):
        """Test content hash computation."""
        hash1 = BookStorage.compute_content_hash(sample_book_data)

        # Same data should produce same hash
        hash2 = BookStorage.compute_content_hash(sample_book_data)
        assert hash1 == hash2

        # Different data should produce different hash
        modified_data = sample_book_data.copy()
        modified_data['price_including_tax'] = 39.99
        hash3 = BookStorage.compute_content_hash(modified_data)
        assert hash1 != hash3

    def test_save_html_snapshot(self, test_db, sample_book_data, sample_html, tmp_path):
        """Test HTML snapshot saving."""
        # Override snapshot directory to temp path
        storage = BookStorage(test_db)
        storage.html_dir = tmp_path

        url = sample_book_data['source_url']
        filepath = storage.save_html_snapshot(sample_html, url)

        # Check file was created
        assert filepath
        assert Path(filepath).exists()

        # Check content
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            assert content == sample_html

    def test_save_book_new(self, test_db, sample_book_data, sample_html, tmp_path):
        """Test saving a new book."""
        storage = BookStorage(test_db)
        storage.html_dir = tmp_path

        book_id = storage.save_book(sample_book_data, sample_html)

        assert book_id is not None

        # Verify book in database
        books_collection = test_db.get_collection('books')
        book = books_collection.find_one({'source_url': sample_book_data['source_url']})

        assert book is not None
        assert book['name'] == sample_book_data['name']
        assert book['price_including_tax'] == sample_book_data['price_including_tax']
        assert 'content_hash' in book

    def test_save_book_update_with_changes(self, test_db, sample_book_data, sample_html, tmp_path):
        """Test updating an existing book with changes."""
        storage = BookStorage(test_db)
        storage.html_dir = tmp_path

        # Save initial book
        book_id1 = storage.save_book(sample_book_data, sample_html)

        # Update price
        updated_data = sample_book_data.copy()
        updated_data['price_including_tax'] = 39.99
        book_id2 = storage.save_book(updated_data, sample_html)

        # Should be same book
        assert book_id1 == book_id2

        # Check changes were logged (should have 2 entries: 'new' and 'updated')
        changes_collection = test_db.get_collection('changes')
        changes = list(changes_collection.find({'book_id': book_id1}))

        assert len(changes) == 2

        # First change should be 'new'
        assert changes[0]['change_type'] == 'new'

        # Second change should be 'updated'
        assert changes[1]['change_type'] == 'updated'
        assert 'price_including_tax' in changes[1]['changed_fields']
        assert changes[1]['changed_fields']['price_including_tax']['old'] == sample_book_data['price_including_tax']
        assert changes[1]['changed_fields']['price_including_tax']['new'] == 39.99

    def test_crawl_state_operations(self, test_db):
        """Test crawl state get/update operations."""
        storage = BookStorage(test_db)

        # Get initial state
        state = storage.get_crawl_state()
        assert state['status'] == 'idle'

        # Update state
        new_state = {
            'status': 'running',
            'last_successful_url': 'https://example.com/page-1',
            'total_books_crawled': 50
        }
        storage.update_crawl_state(new_state)

        # Verify update
        updated_state = storage.get_crawl_state()
        assert updated_state['status'] == 'running'
        assert updated_state['total_books_crawled'] == 50
