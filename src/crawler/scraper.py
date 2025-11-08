"""Async web scraper with retry logic and resumability."""
import asyncio
from typing import List, Optional, Set
from datetime import datetime, timezone
import httpx
from src.utils.logger import get_logger
from src.utils.config import get_settings
from src.utils.database import get_database
from .parser import BookParser
from .storage import BookStorage

logger = get_logger()


class BookScraper:
    """Async web scraper for books.toscrape.com."""

    def __init__(self):
        self.settings = get_settings()
        self.db = get_database()
        self.storage = BookStorage(self.db)
        self.parser = BookParser()
        self.base_url = "https://books.toscrape.com/"
        self.visited_urls: Set[str] = set()
        self.semaphore = asyncio.Semaphore(self.settings.crawler_concurrent_requests)

    async def fetch_with_retry(
        self,
        client: httpx.AsyncClient,
        url: str,
        max_retries: Optional[int] = None
    ) -> Optional[str]:
        """
        Fetch URL with retry logic.

        Args:
            client: HTTP client
            url: URL to fetch
            max_retries: Maximum retry attempts

        Returns:
            HTML content or None if all retries failed
        """
        if max_retries is None:
            max_retries = self.settings.crawler_max_retries

        for attempt in range(max_retries + 1):
            try:
                async with self.semaphore:
                    response = await client.get(
                        url,
                        timeout=self.settings.crawler_request_timeout,
                        follow_redirects=True
                    )
                    response.raise_for_status()
                    logger.debug(f"Successfully fetched: {url}")
                    return response.text

            except httpx.HTTPStatusError as e:
                logger.warning(f"HTTP error {e.response.status_code} for {url} (attempt {attempt + 1}/{max_retries + 1})")
                if e.response.status_code == 404:
                    # Don't retry 404s
                    return None
                if attempt < max_retries:
                    await asyncio.sleep(self.settings.crawler_retry_delay * (attempt + 1))
                else:
                    logger.error(f"Failed to fetch {url} after {max_retries + 1} attempts")
                    return None

            except (httpx.RequestError, httpx.TimeoutException) as e:
                logger.warning(f"Request error for {url}: {e} (attempt {attempt + 1}/{max_retries + 1})")
                if attempt < max_retries:
                    await asyncio.sleep(self.settings.crawler_retry_delay * (attempt + 1))
                else:
                    logger.error(f"Failed to fetch {url} after {max_retries + 1} attempts: {e}")
                    return None

            except Exception as e:
                logger.error(f"Unexpected error fetching {url}: {e}")
                return None

        return None

    async def scrape_book(self, client: httpx.AsyncClient, url: str) -> bool:
        """
        Scrape a single book page.

        Args:
            client: HTTP client
            url: Book page URL

        Returns:
            True if successful, False otherwise
        """
        try:
            # Skip if already visited
            if url in self.visited_urls:
                return True

            # Fetch HTML
            html = await self.fetch_with_retry(client, url)
            if not html:
                return False

            # Parse book data
            book_data = self.parser.parse_book_page(html, url)
            if not book_data:
                logger.warning(f"Failed to parse book data from {url}")
                return False

            # Save book and HTML snapshot
            book_id = self.storage.save_book(book_data, html)
            if book_id:
                self.visited_urls.add(url)
                return True

            return False

        except Exception as e:
            logger.error(f"Error scraping book {url}: {e}")
            return False

    async def scrape_catalog_page(self, client: httpx.AsyncClient, url: str) -> List[str]:
        """
        Scrape a catalog page and extract book links.

        Args:
            client: HTTP client
            url: Catalog page URL

        Returns:
            List of book URLs found on the page
        """
        try:
            html = await self.fetch_with_retry(client, url)
            if not html:
                return []

            # Extract book links (use current page URL for correct relative path resolution)
            book_links = self.parser.extract_book_links(html, url)

            # Check for next page
            next_page_url = self.parser.get_next_page_url(html, url)

            return book_links, next_page_url

        except Exception as e:
            logger.error(f"Error scraping catalog page {url}: {e}")
            return [], None

    async def crawl_all_books(self, resume: bool = False):
        """
        Crawl all books from the website.

        Args:
            resume: Whether to resume from last successful crawl
        """
        try:
            # Update crawler state to running
            self.storage.update_crawl_state({
                'status': 'running',
                'error_message': None
            })

            logger.info("Starting book crawl...")

            # Get starting URL
            start_url = f"{self.base_url}catalogue/page-1.html"

            # Check if we should resume
            if resume:
                state = self.storage.get_crawl_state()
                if state.get('last_successful_url'):
                    start_url = state['last_successful_url']
                    logger.info(f"Resuming from: {start_url}")

            # Create HTTP client
            async with httpx.AsyncClient() as client:
                current_page_url = start_url
                total_books = 0

                # Crawl all catalog pages
                while current_page_url:
                    logger.info(f"Processing catalog page: {current_page_url}")

                    # Get book links from catalog page
                    book_links, next_page_url = await self.scrape_catalog_page(client, current_page_url)

                    if not book_links:
                        logger.warning(f"No book links found on {current_page_url}")
                        break

                    # Scrape books concurrently
                    tasks = [self.scrape_book(client, book_url) for book_url in book_links]
                    results = await asyncio.gather(*tasks, return_exceptions=True)

                    # Count successes
                    successes = sum(1 for r in results if r is True)
                    total_books += successes

                    logger.info(f"Scraped {successes}/{len(book_links)} books from page")

                    # Update state after each page
                    self.storage.update_crawl_state({
                        'last_successful_url': current_page_url,
                        'last_crawl_time': datetime.now(timezone.utc),
                        'total_books_crawled': total_books,
                        'status': 'running'
                    })

                    # Move to next page
                    current_page_url = next_page_url

                # Crawl completed successfully
                self.storage.update_crawl_state({
                    'status': 'completed',
                    'last_crawl_time': datetime.now(timezone.utc),
                    'total_books_crawled': total_books,
                    'error_message': None
                })

                logger.info(f"Crawl completed! Total books processed: {total_books}")

        except Exception as e:
            logger.error(f"Crawl failed: {e}")
            self.storage.update_crawl_state({
                'status': 'failed',
                'error_message': str(e)
            })
            raise

    async def crawl_for_changes(self):
        """
        Crawl all books to detect changes.
        This is used by the scheduler.
        """
        logger.info("Starting change detection crawl...")
        await self.crawl_all_books(resume=False)
        logger.info("Change detection crawl completed")


async def main():
    """Main function for running crawler standalone."""
    scraper = BookScraper()
    await scraper.crawl_all_books()


if __name__ == "__main__":
    from src.utils.logger import setup_logger
    setup_logger()
    asyncio.run(main())
