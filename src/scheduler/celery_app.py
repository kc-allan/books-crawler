"""Celery application configuration."""
from celery import Celery
from celery.schedules import crontab
from src.utils.config import get_settings

settings = get_settings()

# Create Celery app
celery_app = Celery(
    'books_crawler',
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=['src.scheduler.tasks']
)

# Configure Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max
    task_soft_time_limit=3300,  # 55 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
)

# Configure periodic tasks (Beat schedule)
celery_app.conf.beat_schedule = {
    'daily-crawl': {
        'task': 'src.scheduler.tasks.crawl_books_task',
        'schedule': crontab(
            hour=settings.scheduler_crawl_hour,
            minute=settings.scheduler_crawl_minute
        ),
        'options': {'expires': 3600}
    },
    'daily-change-report': {
        'task': 'src.scheduler.tasks.generate_change_report',
        'schedule': crontab(
            hour=settings.scheduler_crawl_hour + 1,  # 1 hour after crawl
            minute=settings.scheduler_crawl_minute
        ),
        'options': {'expires': 3600}
    },
}

if __name__ == '__main__':
    celery_app.start()
