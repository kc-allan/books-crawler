"""Script to run the crawler."""
import sys
import asyncio
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.crawler.scraper import BookScraper
from src.utils.logger import setup_logger, get_logger

setup_logger()
logger = get_logger()


async def main():
    """Run the crawler."""
    try:
        logger.info("Starting book crawler...")
        scraper = BookScraper()
        await scraper.crawl_all_books(resume=True)
        logger.info("Crawler completed successfully!")

    except KeyboardInterrupt:
        logger.info("Crawler interrupted by user")
    except Exception as e:
        logger.error(f"Crawler failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
