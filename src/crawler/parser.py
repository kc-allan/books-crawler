"""HTML parsing logic for book pages."""
import re
from typing import Optional, Dict, Any
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from src.utils.logger import get_logger

logger = get_logger()


class BookParser:
    """Parse book information from HTML."""

    RATING_MAP = {
        "One": 1,
        "Two": 2,
        "Three": 3,
        "Four": 4,
        "Five": 5
    }

    @staticmethod
    def parse_book_page(html: str, url: str) -> Optional[Dict[str, Any]]:
        """
        Parse a book detail page and extract all information.

        Args:
            html: HTML content of the book page
            url: URL of the book page

        Returns:
            Dictionary with book data or None if parsing fails
        """
        try:
            soup = BeautifulSoup(html, 'lxml')

            # Extract book name
            name_elem = soup.select_one('div.product_main h1')
            if not name_elem:
                logger.warning(f"Could not find book name in {url}")
                return None
            name = name_elem.text.strip()

            # Extract description
            description_elem = soup.select_one('#product_description ~ p')
            description = description_elem.text.strip() if description_elem and description_elem.text else ""

            # Extract category
            breadcrumb = soup.select('ul.breadcrumb li')
            category = breadcrumb[2].text.strip() if len(breadcrumb) > 2 else "Unknown"

            # Extract product information table
            product_info = {}
            info_table = soup.select('table.table-striped tr')
            for row in info_table:
                header = row.select_one('th')
                value = row.select_one('td')
                if header and value:
                    product_info[header.text.strip()] = value.text.strip()

            # Extract prices
            price_including_tax = BookParser._parse_price(
                product_info.get('Price (incl. tax)', '£0.00')
            )
            price_excluding_tax = BookParser._parse_price(
                product_info.get('Price (excl. tax)', '£0.00')
            )

            # Extract availability
            availability = product_info.get('Availability', 'Unknown')

            # Extract number of reviews
            number_of_reviews = int(product_info.get('Number of reviews', 0))

            # Extract image URL
            image_elem = soup.select_one('div.item.active img')
            image_url = ""
            if image_elem and image_elem.get('src'):
                # Convert relative URL to absolute
                image_url = urljoin('https://books.toscrape.com/', image_elem['src'])

            # Extract rating
            rating_elem = soup.select_one('p.star-rating')
            rating = 0
            if rating_elem:
                rating_class = rating_elem.get('class', [])
                for cls in rating_class:
                    if cls in BookParser.RATING_MAP:
                        rating = BookParser.RATING_MAP[cls]
                        break

            return {
                "name": name,
                "description": description,
                "category": category,
                "price_including_tax": price_including_tax,
                "price_excluding_tax": price_excluding_tax,
                "availability": availability,
                "number_of_reviews": number_of_reviews,
                "image_url": image_url,
                "rating": rating,
                "source_url": url
            }

        except Exception as e:
            logger.error(f"Error parsing book page {url}: {e}")
            return None

    @staticmethod
    def _parse_price(price_str: str) -> float:
        """Extract numeric price from string like '£51.77'."""
        try:
            # Remove currency symbols and whitespace
            price_clean = re.sub(r'[^\d.]', '', price_str)
            return float(price_clean)
        except (ValueError, AttributeError):
            return 0.0

    @staticmethod
    def extract_book_links(html: str, base_url: str = "https://books.toscrape.com/") -> list[str]:
        """
        Extract all book detail page links from a catalog page.

        Args:
            html: HTML content of the catalog page
            base_url: Base URL for resolving relative links

        Returns:
            List of absolute URLs to book pages
        """
        try:
            soup = BeautifulSoup(html, 'lxml')
            book_links = []

            # Find all book article elements
            articles = soup.select('article.product_pod')
            for article in articles:
                link_elem = article.select_one('h3 a')
                if link_elem and link_elem.get('href'):
                    # Convert relative URL to absolute
                    relative_url = link_elem['href']
                    absolute_url = urljoin(base_url, relative_url)
                    book_links.append(absolute_url)

            logger.info(f"Extracted {len(book_links)} book links from catalog page")
            return book_links

        except Exception as e:
            logger.error(f"Error extracting book links: {e}")
            return []

    @staticmethod
    def get_next_page_url(html: str, current_url: str) -> Optional[str]:
        """
        Extract the 'next' page URL from pagination.

        Args:
            html: HTML content of the catalog page
            current_url: Current page URL

        Returns:
            Next page URL or None if no next page
        """
        try:
            soup = BeautifulSoup(html, 'lxml')
            next_elem = soup.select_one('li.next a')

            if next_elem and next_elem.get('href'):
                next_url = urljoin(current_url, next_elem['href'])
                return next_url

            return None

        except Exception as e:
            logger.error(f"Error extracting next page URL: {e}")
            return None
