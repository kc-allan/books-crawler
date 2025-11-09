"""Unit tests for book parser."""
import pytest
from src.crawler.parser import BookParser


class TestBookParser:
    """Test BookParser class."""

    def test_parse_price(self):
        """Test price parsing from string."""
        assert BookParser._parse_price("£29.99") == 29.99
        assert BookParser._parse_price("£100.00") == 100.00
        assert BookParser._parse_price("$15.50") == 15.50
        assert BookParser._parse_price("invalid") == 0.0

    def test_parse_book_page(self, sample_html):
        """Test parsing a complete book page."""
        url = "https://books.toscrape.com/test/book.html"
        book_data = BookParser.parse_book_page(sample_html, url)

        assert book_data is not None
        assert book_data['name'] == "Test Book"
        assert book_data['category'] == "Fiction"
        assert book_data['price_including_tax'] == 29.99
        assert book_data['rating'] == 4
        assert book_data['number_of_reviews'] == 5

    def test_parse_book_page_invalid_html(self):
        """Test parsing invalid HTML."""
        invalid_html = "<html><body>Invalid</body></html>"
        url = "https://books.toscrape.com/test/book.html"
        book_data = BookParser.parse_book_page(invalid_html, url)

        assert book_data is None

    def test_extract_book_links(self):
        """Test extracting book links from catalog page."""
        catalog_html = """
        <html>
            <body>
                <article class="product_pod">
                    <h3><a href="catalogue/book1.html">Book 1</a></h3>
                </article>
                <article class="product_pod">
                    <h3><a href="catalogue/book2.html">Book 2</a></h3>
                </article>
            </body>
        </html>
        """

        links = BookParser.extract_book_links(catalog_html)

        assert len(links) == 2
        assert "https://books.toscrape.com/catalogue/book1.html" in links
        assert "https://books.toscrape.com/catalogue/book2.html" in links

    def test_get_next_page_url(self):
        """Test extracting next page URL."""
        html_with_next = """
        <html>
            <body>
                <li class="next"><a href="page-2.html">next</a></li>
            </body>
        </html>
        """

        current_url = "https://books.toscrape.com/catalogue/page-1.html"
        next_url = BookParser.get_next_page_url(html_with_next, current_url)

        assert next_url is not None
        assert "page-2.html" in next_url

    def test_get_next_page_url_no_next(self):
        """Test when there's no next page."""
        html_without_next = "<html><body></body></html>"
        current_url = "https://books.toscrape.com/catalogue/page-1.html"
        next_url = BookParser.get_next_page_url(html_without_next, current_url)

        assert next_url is None

    def test_rating_map(self):
        """Test rating mapping."""
        assert BookParser.RATING_MAP["One"] == 1
        assert BookParser.RATING_MAP["Two"] == 2
        assert BookParser.RATING_MAP["Three"] == 3
        assert BookParser.RATING_MAP["Four"] == 4
        assert BookParser.RATING_MAP["Five"] == 5
