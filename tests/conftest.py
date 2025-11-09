"""Pytest configuration and fixtures."""
import pytest
import asyncio
from typing import Generator
from pymongo import MongoClient
from src.utils.config import get_settings
from src.utils.database import Database


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def settings():
    """Get test settings."""
    return get_settings()


@pytest.fixture(scope="function")
def test_db(settings) -> Generator[Database, None, None]:
    """Create a test database instance.

    Each test gets a fresh database to ensure isolation.
    Database is automatically cleaned up after the test.
    """
    # Use a separate test database with unique name per test
    import time
    test_db_name = f"{settings.mongodb_db}_test_{int(time.time() * 1000)}"

    # Create test database connection
    client = MongoClient(settings.mongodb_url, serverSelectionTimeoutMS=5000)

    db = Database()
    db.client = client
    db.db = client[test_db_name]
    db.settings = settings

    yield db

    # Cleanup: Always clean up test data
    try:
        if test_db_name in client.list_database_names():
            client.drop_database(test_db_name)
    except Exception as e:
        # Log the error but don't fail the test
        print(f"Warning: Failed to drop test database {test_db_name}: {e}")
    finally:
        try:
            client.close()
        except Exception as e:
            print(f"Warning: Failed to close MongoDB client: {e}")


@pytest.fixture
def sample_book_data():
    """Sample book data for testing."""
    return {
        "name": "Test Book",
        "description": "A test book description",
        "category": "Fiction",
        "price_including_tax": 29.99,
        "price_excluding_tax": 29.99,
        "availability": "In stock (10 available)",
        "number_of_reviews": 5,
        "image_url": "https://example.com/image.jpg",
        "rating": 4,
        "source_url": "https://books.toscrape.com/test/book.html"
    }


@pytest.fixture
def sample_html():
    """Sample HTML for book page."""
    return """
    <html>
        <body>
            <div class="product_main">
                <h1>Test Book</h1>
                <p class="star-rating Four"></p>
            </div>
            <div id="product_description"></div>
            <p>A test book description</p>
            <ul class="breadcrumb">
                <li><a href="/">Home</a></li>
                <li><a href="/books">Books</a></li>
                <li><a href="/fiction">Fiction</a></li>
            </ul>
            <table class="table-striped">
                <tr><th>Price (incl. tax)</th><td>£29.99</td></tr>
                <tr><th>Price (excl. tax)</th><td>£29.99</td></tr>
                <tr><th>Availability</th><td>In stock (10 available)</td></tr>
                <tr><th>Number of reviews</th><td>5</td></tr>
            </table>
            <div class="item active">
                <img src="../../media/cache/test.jpg" alt="Test Book"/>
            </div>
        </body>
    </html>
    """
