"""Celery tasks for scheduled crawling and reporting."""
import asyncio
import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Any
from .celery_app import celery_app
from src.utils.logger import get_logger, setup_logger
from src.utils.database import get_database
from src.crawler.scraper import BookScraper

# Setup logger for tasks
setup_logger()
logger = get_logger()


@celery_app.task(name='src.scheduler.tasks.crawl_books_task', bind=True, soft_time_limit=600, time_limit=720)
def crawl_books_task(self):
    """
    Scheduled task to crawl books and detect changes.
    Runs daily at configured time.
    """
    try:
        logger.info("Starting scheduled book crawl task...")

        # Run async crawler
        scraper = BookScraper()
        asyncio.run(scraper.crawl_for_changes())

        logger.info("Scheduled book crawl completed successfully")
        return {"status": "success", "timestamp": datetime.now(timezone.utc).isoformat()}

    except Exception as e:
        logger.error(f"Scheduled crawl task failed: {e}")
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries), max_retries=3)


@celery_app.task(name='src.scheduler.tasks.generate_change_report', bind=True, soft_time_limit=600, time_limit=720)
def generate_change_report(self, format: str = 'json'):
    """
    Generate a daily change report.

    Args:
        format: Output format ('json' or 'csv')

    Returns:
        Report data or file path
    """
    try:
        logger.info(f"Generating daily change report in {format} format...")

        db = get_database()
        changes_collection = db.get_collection('changes')

        # Get changes from last 24 hours
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        changes = list(changes_collection.find(
            {'timestamp': {'$gte': yesterday}},
            {'_id': 0}  # Exclude MongoDB ID
        ).sort('timestamp', -1))

        # Convert datetime objects to strings for serialization
        for change in changes:
            if isinstance(change.get('timestamp'), datetime):
                change['timestamp'] = change['timestamp'].isoformat()

        # Create reports directory
        reports_dir = Path('reports')
        reports_dir.mkdir(exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')

        if format == 'json':
            # Generate JSON report
            report_path = reports_dir / f'change_report_{timestamp}.json'
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'report_date': datetime.now(timezone.utc).isoformat(),
                    'total_changes': len(changes),
                    'changes': changes
                }, f, indent=2)

            logger.info(f"JSON report generated: {report_path}")
            return str(report_path)

        elif format == 'csv':
            # Generate CSV report
            report_path = reports_dir / f'change_report_{timestamp}.csv'

            # Flatten the data for CSV
            flattened_changes = []
            for change in changes:
                base_data = {
                    'timestamp': change.get('timestamp'),
                    'book_id': change.get('book_id'),
                    'book_name': change.get('book_name'),
                    'change_type': change.get('change_type')
                }

                # Add changed fields
                changed_fields = change.get('changed_fields', {})
                if changed_fields:
                    for field, values in changed_fields.items():
                        flattened_changes.append({
                            **base_data,
                            'field': field,
                            'old_value': values.get('old'),
                            'new_value': values.get('new')
                        })
                else:
                    flattened_changes.append({
                        **base_data,
                        'field': 'N/A',
                        'old_value': 'N/A',
                        'new_value': 'N/A'
                    })

            # Write CSV
            if flattened_changes:
                with open(report_path, 'w', newline='', encoding='utf-8') as f:
                    fieldnames = ['timestamp', 'book_id', 'book_name', 'change_type', 'field', 'old_value', 'new_value']
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(flattened_changes)

            logger.info(f"CSV report generated: {report_path}")
            return str(report_path)

        else:
            raise ValueError(f"Unsupported format: {format}")

    except Exception as e:
        logger.error(f"Failed to generate change report: {e}")
        raise self.retry(exc=e, countdown=60, max_retries=2)


@celery_app.task(name='src.scheduler.tasks.send_change_alert')
def send_change_alert(changes: List[Dict[str, Any]]):
    """
    Send alert when significant changes are detected.

    Args:
        changes: List of change records
    """
    try:
        # Count significant changes
        new_books = sum(1 for c in changes if c.get('change_type') == 'new')
        price_changes = sum(1 for c in changes
                          if 'price_including_tax' in c.get('changed_fields', {})
                          or 'price_excluding_tax' in c.get('changed_fields', {}))

        if new_books > 0 or price_changes > 0:
            alert_message = f"""
            Daily Change Alert:
            - New books: {new_books}
            - Price changes: {price_changes}
            - Total changes: {len(changes)}
            """

            logger.warning(alert_message)

            # In production, this would send an email or notification
            # For now, we just log it
            # email.send(subject="Book Changes Detected", body=alert_message)

        return {"new_books": new_books, "price_changes": price_changes}

    except Exception as e:
        logger.error(f"Failed to send change alert: {e}")
        return None
