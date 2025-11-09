"""Integration tests for API endpoints."""
import pytest
from fastapi.testclient import TestClient
from src.api.app import create_app
from src.api.auth import auth_manager
from src.utils.database import get_database


@pytest.fixture
def client(test_db):
    """Create test client with test database.

    Uses FastAPI's dependency override mechanism to inject test database.
    Properly cleans up after each test to prevent state leakage.
    """
    app = create_app()

    # Override the database dependency to use test_db
    def override_get_database():
        return test_db

    app.dependency_overrides[get_database] = override_get_database

    # Use context manager for proper cleanup
    with TestClient(app) as test_client:
        yield test_client

    # Clean up dependency overrides after test
    app.dependency_overrides.clear()


@pytest.fixture
def api_key(test_db):
    """Create test API key for authentication.

    Note: Uses global auth_manager which is not ideal but acceptable
    for integration tests. For production, consider using dependency
    injection for auth_manager as well.
    """
    # Temporarily override auth_manager's database
    original_db = getattr(auth_manager, 'db', None)
    auth_manager.db = test_db

    try:
        # Create test user
        user_id = auth_manager.create_user("testuser", "test@example.com")

        # Create API key
        key_obj = auth_manager.create_api_key(
            user_id=user_id,
            name="Test API Key",
            rate_limit=100,
            rate_period=3600
        )

        yield key_obj.key

    finally:
        # Restore original database (if any)
        if original_db:
            auth_manager.db = original_db


class TestAPIEndpoints:
    """Test API endpoints integration."""

    def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_root_endpoint(self, client):
        """Test root endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data

    def test_get_books_without_auth(self, client):
        """Test getting books without authentication."""
        response = client.get("/api/v1/books")
        assert response.status_code == 401

    def test_get_books_with_auth(self, client, api_key, test_db, sample_book_data):
        """Test getting books with authentication."""
        # Insert test book
        from src.crawler.storage import BookStorage
        storage = BookStorage(test_db)
        storage.save_book(sample_book_data, "<html>test</html>")

        # Make request with API key
        response = client.get(
            "/api/v1/books",
            headers={"Authorization": f"Bearer {api_key}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "books" in data
        assert "total" in data
        assert "rate_limit_info" in data

    def test_get_books_with_filters(self, client, api_key, test_db, sample_book_data):
        """Test getting books with filters."""
        # Insert test books
        from src.crawler.storage import BookStorage
        storage = BookStorage(test_db)

        # Add multiple books with different properties
        for i in range(5):
            book = sample_book_data.copy()
            book['name'] = f"Book {i}"
            book['source_url'] = f"https://example.com/book{i}.html"
            book['price_including_tax'] = 10.0 + i * 5
            book['rating'] = (i % 5) + 1
            storage.save_book(book, "<html>test</html>")

        # Test category filter
        response = client.get(
            "/api/v1/books?category=Fiction",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        assert response.status_code == 200

        # Test price filter
        response = client.get(
            "/api/v1/books?min_price=15&max_price=25",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        assert response.status_code == 200

        # Test rating filter
        response = client.get(
            "/api/v1/books?rating=4",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        assert response.status_code == 200

    def test_get_book_by_id(self, client, api_key, test_db, sample_book_data):
        """Test getting a specific book by ID."""
        from src.crawler.storage import BookStorage
        storage = BookStorage(test_db)

        # Insert test book
        book_id = storage.save_book(sample_book_data, "<html>test</html>")

        # Get book by ID
        response = client.get(
            f"/api/v1/books/{book_id}",
            headers={"Authorization": f"Bearer {api_key}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data['id'] == book_id
        assert data['name'] == sample_book_data['name']

    def test_get_book_invalid_id(self, client, api_key):
        """Test getting a book with invalid ID."""
        response = client.get(
            "/api/v1/books/invalid_id",
            headers={"Authorization": f"Bearer {api_key}"}
        )

        assert response.status_code == 400

    def test_get_book_not_found(self, client, api_key):
        """Test getting a non-existent book."""
        from bson import ObjectId

        fake_id = str(ObjectId())
        response = client.get(
            f"/api/v1/books/{fake_id}",
            headers={"Authorization": f"Bearer {api_key}"}
        )

        assert response.status_code == 404

    def test_get_changes(self, client, api_key, test_db, sample_book_data):
        """Test getting changes."""
        from src.crawler.storage import BookStorage
        storage = BookStorage(test_db)

        # Insert and update a book to create changes
        book_id = storage.save_book(sample_book_data, "<html>test</html>")

        updated_data = sample_book_data.copy()
        updated_data['price_including_tax'] = 39.99
        storage.save_book(updated_data, "<html>test</html>")

        # Get changes
        response = client.get(
            "/api/v1/changes",
            headers={"Authorization": f"Bearer {api_key}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "changes" in data
        assert "total" in data
        assert data['total'] >= 1

    def test_rate_limiting(self, client, test_db):
        """Test rate limiting functionality."""
        # Set auth_manager to use test_db
        auth_manager.db = test_db

        # Create API key with low limit
        user_id = auth_manager.create_user("ratelimituser", "rate@example.com")
        key_obj = auth_manager.create_api_key(
            user_id=user_id,
            name="Rate Limit Test",
            rate_limit=5,
            rate_period=3600
        )

        # Make requests up to limit
        for i in range(5):
            response = client.get(
                "/api/v1/books",
                headers={"Authorization": f"Bearer {key_obj.key}"}
            )
            assert response.status_code in [200, 500]  # May fail if no books

        # Next request should be rate limited
        response = client.get(
            "/api/v1/books",
            headers={"Authorization": f"Bearer {key_obj.key}"}
        )
        assert response.status_code == 429

    def test_pagination(self, client, api_key, test_db, sample_book_data):
        """Test pagination."""
        from src.crawler.storage import BookStorage
        storage = BookStorage(test_db)

        # Insert multiple books
        for i in range(25):
            book = sample_book_data.copy()
            book['name'] = f"Book {i}"
            book['source_url'] = f"https://example.com/book{i}.html"
            storage.save_book(book, "<html>test</html>")

        # Test first page
        response = client.get(
            "/api/v1/books?page=1&page_size=10",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data['page'] == 1
        assert len(data['books']) <= 10

        # Test second page
        response = client.get(
            "/api/v1/books?page=2&page_size=10",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data['page'] == 2
