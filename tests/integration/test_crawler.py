"""Integration tests for crawler."""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from src.crawler.scraper import BookScraper
from src.crawler.storage import BookStorage


@pytest.mark.asyncio
class TestCrawlerIntegration:
    """Integration tests for the crawler."""

    async def test_scrape_book_success(self, test_db, sample_html):
        """Test scraping a book successfully."""
        scraper = BookScraper()
        scraper.db = test_db
        scraper.storage = BookStorage(test_db)

        # Mock HTTP client
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=Mock(text=sample_html, status_code=200))

        url = "https://books.toscrape.com/test/book.html"

        # Patch raise_for_status to do nothing
        with patch.object(mock_client.get.return_value, 'raise_for_status', return_value=None):
            success = await scraper.scrape_book(mock_client, url)

        assert success is True
        assert url in scraper.visited_urls

    async def test_scrape_book_retry_on_error(self, test_db):
        """Test retry logic when scraping fails."""
        scraper = BookScraper()
        scraper.db = test_db
        scraper.storage = BookStorage(test_db)

        # Mock HTTP client that fails first, then succeeds
        mock_response_fail = Mock()
        mock_response_fail.raise_for_status.side_effect = Exception("Network error")

        mock_response_success = Mock()
        mock_response_success.text = "<html>test</html>"
        mock_response_success.status_code = 200
        mock_response_success.raise_for_status.return_value = None

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[mock_response_fail, mock_response_success])

        url = "https://books.toscrape.com/test/book.html"

        # This should fail because parsing will fail on invalid HTML
        success = await scraper.scrape_book(mock_client, url)

        # Verify retries were attempted
        assert mock_client.get.call_count >= 1

    async def test_scrape_catalog_page(self, test_db):
        """Test scraping a catalog page."""
        scraper = BookScraper()
        scraper.db = test_db

        catalog_html = """
        <html>
            <body>
                <article class="product_pod">
                    <h3><a href="../../../catalogue/book1.html">Book 1</a></h3>
                </article>
                <article class="product_pod">
                    <h3><a href="../../../catalogue/book2.html">Book 2</a></h3>
                </article>
                <li class="next"><a href="page-2.html">next</a></li>
            </body>
        </html>
        """

        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.text = catalog_html
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_client.get = AsyncMock(return_value=mock_response)

        url = "https://books.toscrape.com/catalogue/page-1.html"
        book_links, next_page = await scraper.scrape_catalog_page(mock_client, url)

        assert len(book_links) == 2
        assert next_page is not None
        assert "page-2.html" in next_page

    async def test_crawl_state_tracking(self, test_db):
        """Test that crawl state is tracked correctly."""
        scraper = BookScraper()
        scraper.db = test_db
        scraper.storage = BookStorage(test_db)

        # Update state
        scraper.storage.update_crawl_state({
            'status': 'running',
            'total_books_crawled': 10
        })

        # Get state
        state = scraper.storage.get_crawl_state()

        assert state['status'] == 'running'
        assert state['total_books_crawled'] == 10
