# Books Crawler - Web Scraping System

A comprehensive, scalable web crawling solution for monitoring book information from books.toscrape.com with RESTful APIs, change detection, and scheduled crawling.

## Features

- **Async Web Crawler**: High-performance async crawler with retry logic and fault tolerance
- **Change Detection**: Automatic detection of price changes, new books, and updates
- **RESTful API**: FastAPI-based API with filtering, sorting, and pagination
- **Authentication**: API key-based authentication with MongoDB storage
- **Rate Limiting**: Per-API-key rate limiting with configurable thresholds
- **Scheduled Crawling**: Celery + Redis for daily automated crawls
- **Data Persistence**: MongoDB for structured data, filesystem for HTML snapshots
- **Comprehensive Testing**: Unit and integration tests with pytest

### MongoDB Documents snapshot

![MongoDB Collections](assets/documents_snippet.png)

### Sample crawl output
![Crawled Output](assets/sample_run.png)

## Project Structure

```
submission/
├── src/
│   ├── crawler/          # Web crawler modules
│   │   ├── __init__.py
│   │   ├── parser.py     # HTML parsing logic
│   │   ├── scraper.py    # Async scraper with retry
│   │   └── storage.py    # Data and HTML storage
│   ├── scheduler/        # Celery tasks and scheduling
│   │   ├── __init__.py
│   │   ├── celery_app.py # Celery configuration
│   │   └── tasks.py      # Scheduled tasks
│   ├── api/              # FastAPI application
│   │   ├── __init__.py
│   │   ├── app.py        # FastAPI app setup
│   │   ├── auth.py       # Authentication logic
│   │   ├── rate_limiter.py # Rate limiting
│   │   └── routes.py     # API endpoints
│   ├── models/           # Pydantic models
│   │   ├── __init__.py
│   │   ├── book.py       # Book models
│   │   └── user.py       # User/API key models
│   └── utils/            # Utility modules
│       ├── __init__.py
│       ├── config.py     # Configuration management
│       ├── database.py   # MongoDB connection
│       └── logger.py     # Logging setup
├── tests/
│   ├── unit/             # Unit tests
│   │   ├── test_parser.py
│   │   ├── test_storage.py
│   │   ├── test_auth.py
│   │   └── test_rate_limiter.py
│   ├── integration/      # Integration tests
│   │   ├── test_api.py
│   │   └── test_crawler.py
│   └── conftest.py       # Test fixtures
├── logs/                 # Application logs
├── html_snapshots/       # HTML snapshots
├── reports/              # Change reports
├── requirements.txt      # Python dependencies
├── .env.example          # Example environment config
└── README.md             # This file
```

## Requirements

### Minimum Software Requirements

- **Python**: 3.11+
- **MongoDB**: 4.4+ (running locally on port 27017)
- **Redis**: 6.0+ (for Celery task queue)

### Python Dependencies

See [requirements.txt](requirements.txt) for full list.

## Installation & Setup

### 1. Clone the Repository

```bash
git clone <repository-url>
```

### 2. Create Virtual Environment

```bash
python -m venv venv

# On Windows
venv\Scripts\activate

# On Linux/Mac
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Setup MongoDB

Ensure MongoDB is running locally:

```bash
# Check MongoDB status
mongosh --eval "db.runCommand({ ping: 1 })"
```

### 5. Setup Redis

Ensure Redis is running locally:

```bash
# On Windows (with Redis installed)
redis-server

# On Linux
sudo systemctl start redis

# Check Redis
redis-cli ping
```

### 6. Configure Environment

Copy the example environment file and customize:

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```env
# MongoDB Configuration
MONGODB_HOST=localhost
MONGODB_PORT=27017
MONGODB_DB=books_crawler

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379

# Crawler Configuration
CRAWLER_MAX_RETRIES=3
CRAWLER_CONCURRENT_REQUESTS=10

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000

# Rate Limiting
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_PERIOD=3600

# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

## Usage

### Running the Crawler

Run a one-time crawl:

```bash
python -m src.crawler.scraper
```

The crawler will:
- Crawl all books from books.toscrape.com
- Store data in MongoDB
- Save HTML snapshots to `html_snapshots/`
- Support resume from last successful page on failure

### Starting the API Server

```bash
python -m src.api.app
```

Or using uvicorn directly:

```bash
uvicorn src.api.app:app --host 0.0.0.0 --port 8000 --reload
```

Access:
- **API Documentation**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

### Setting Up API Keys

Before using the API, create a user and API key through the API's user management endpoints or directly in MongoDB:

Save the API key as you'll need it for all API requests!

### Running the Scheduler

Start Celery worker:

```bash
celery -A src.scheduler.celery_app worker --loglevel=info
```

Start Celery Beat (scheduler):

```bash
celery -A src.scheduler.celery_app beat --loglevel=info
```

Or run both together (for development):

```bash
celery -A src.scheduler.celery_app worker --beat --loglevel=info
```

The scheduler will:
- Run daily crawls at 2:00 AM UTC (configurable)
- Generate change reports at 3:00 AM UTC
- Detect new books and price changes
- Store change logs in MongoDB

*Note*: This is best set up as background services in production. Recommended configurations are provided in the [celery-worker.service](celery-worker.service.template) and [celery-beat.service](celery-beat.service.template) templates.

### Manual Task Execution

Trigger tasks manually:

```python
from src.scheduler.tasks import crawl_books_task, generate_change_report

# Run crawl task
result = crawl_books_task.delay()
print(result.get())

# Generate change report
report_path = generate_change_report.delay(format='json')
print(report_path.get())
```

## API Usage

### Authentication

All API endpoints require authentication via Bearer token in the header:

```bash
curl -H "Authorization: Bearer sk_live_your_api_key_here" http://localhost:8000/api/v1/books
```

### API Endpoints

#### 1. Get Books (with filtering & pagination)

```bash
# Get all books
curl -H "Authorization: Bearer YOUR_KEY" "http://localhost:8000/api/v1/books"

# Filter by category
curl -H "Authorization: Bearer YOUR_KEY" "http://localhost:8000/api/v1/books?category=Fiction"

# Filter by price range
curl -H "Authorization: Bearer YOUR_KEY" "http://localhost:8000/api/v1/books?min_price=10&max_price=30"

# Filter by rating
curl -H "Authorization: Bearer YOUR_KEY" "http://localhost:8000/api/v1/books?rating=5"

# Sort by price
curl -H "Authorization: Bearer YOUR_KEY" "http://localhost:8000/api/v1/books?sort_by=price"

# Pagination
curl -H "Authorization: Bearer YOUR_KEY" "http://localhost:8000/api/v1/books?page=2&page_size=20"

# Combined filters
curl -H "Authorization: Bearer YOUR_KEY" "http://localhost:8000/api/v1/books?category=Fiction&min_price=15&rating=4&sort_by=rating&page=1"
```

#### 2. Get Book by ID

```bash
curl -H "Authorization: Bearer YOUR_KEY" "http://localhost:8000/api/v1/books/{book_id}"
```

#### 3. Get Changes

```bash
# Get all recent changes (last 7 days)
curl -H "Authorization: Bearer YOUR_KEY" "http://localhost:8000/api/v1/changes"

# Filter by change type
curl -H "Authorization: Bearer YOUR_KEY" "http://localhost:8000/api/v1/changes?change_type=new"
curl -H "Authorization: Bearer YOUR_KEY" "http://localhost:8000/api/v1/changes?change_type=updated"

# Custom date range (last 30 days)
curl -H "Authorization: Bearer YOUR_KEY" "http://localhost:8000/api/v1/changes?days=30"

# Pagination
curl -H "Authorization: Bearer YOUR_KEY" "http://localhost:8000/api/v1/changes?page=1&page_size=50"
```

### Response Format

All responses include rate limit information:

```json
{
  "total": 1000,
  "page": 1,
  "page_size": 20,
  "total_pages": 50,
  "books": [...],
  "rate_limit_info": {
    "remaining": 95,
    "limit": 100,
    "reset_time": "2024-01-01T13:00:00"
  }
}
```

### Rate Limits

- Default: 100 requests per hour per API key
- Configurable per API key
- Returns 429 status code when exceeded
- Reset time provided in response headers

## MongoDB Schema

### Books Collection

```javascript
{
  "_id": ObjectId,
  "name": "Book Name",
  "description": "Book description...",
  "category": "Fiction",
  "price_including_tax": 29.99,
  "price_excluding_tax": 29.99,
  "availability": "In stock (22 available)",
  "number_of_reviews": 10,
  "image_url": "https://...",
  "rating": 4,
  "source_url": "https://books.toscrape.com/...",
  "crawl_timestamp": ISODate("2024-01-01T00:00:00Z"),
  "last_updated": ISODate("2024-01-01T12:00:00Z"),
  "status": "active",
  "content_hash": "abc123...",
  "html_snapshot_path": "html_snapshots/book_xyz.html"
}
```

### Changes Collection

```javascript
{
  "book_id": "507f1f77bcf86cd799439011",
  "book_name": "Book Name",
  "change_type": "updated",  // or "new"
  "changed_fields": {
    "price_including_tax": {
      "old": 29.99,
      "new": 24.99
    },
    "availability": {
      "old": "In stock (22 available)",
      "new": "In stock (15 available)"
    }
  },
  "timestamp": ISODate("2024-01-01T12:00:00Z")
}
```

## Testing

### Run All Tests

```bash
pytest
```

### Run with Coverage

```bash
pytest --cov=src --cov-report=html
```

### Run Specific Test Categories

```bash
# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# Specific test file
pytest tests/unit/test_parser.py

# Specific test
pytest tests/unit/test_parser.py::TestBookParser::test_parse_price
```

### Test Coverage

The project includes comprehensive test coverage:

- **Unit Tests**: Parser, storage, authentication, rate limiting
- **Integration Tests**: API endpoints, crawler workflow
- **Fixtures**: Reusable test data and database setup

## Logging

Logs are stored in `logs/app.log` with rotation:

- **Rotation**: 10 MB per file
- **Retention**: 30 days
- **Compression**: Automatic zip compression
- **Levels**: DEBUG, INFO, WARNING, ERROR

View logs:

```bash
# Real-time log monitoring
tail -f logs/app.log

# Filter by level
grep "ERROR" logs/app.log
```

## Contributing

1. Follow PEP 8 style guidelines
2. Add tests for new features
3. Update documentation
4. Use type hints
5. Run tests before committing

## License

MIT License - See [LICENSE](LICENSE) file for details

## Support

For issues, questions, or contributions:
- Create an issue in the repository
- Contact: kiruiallan401@gmail.com

---

**Built with**: Python 3.12, FastAPI, MongoDB, Celery, Redis
