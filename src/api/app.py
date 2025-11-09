"""FastAPI application setup."""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from src.utils.logger import setup_logger, get_logger
from src.utils.database import get_database
from .routes import router
from .rate_limiter import rate_limiter

# Setup logger 
setup_logger()
logger = get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Starting Books Crawler API...")
    try:
        db = get_database()
        logger.info("Database connected successfully")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down Books Crawler API...")
    try:
        db = get_database()
        db.disconnect()
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""

    app = FastAPI(
        title="Books Crawler API",
        description="""
        A web crawling API for books.toscrape.com.

        ## Features

        - **Book Catalog**: Search, filter, and retrieve book information
        - **Change Tracking**: Monitor price changes and new additions
        - **Bearer Token Authentication**: Secure API key-based authentication
        - **Rate Limiting**: Per-API-key rate limiting
        - **User Management**: Register users and create API keys via API

        ## Getting Started

        1. **Register a user**: `POST /api/v1/auth/register`
        2. **Create an API key**: `POST /api/v1/auth/create-key` (use the user_id from step 1)
        3. **Use the API**: Include the API key as a Bearer token in all requests

        ## Authentication

        All book and change endpoints require Bearer token authentication.

        Include the token in the `Authorization` header:

        ```
        Authorization: Bearer sk_live_your_api_key_here
        ```

        ### Quick Example

        ```bash
        # 1. Register user
        curl -X POST http://localhost:8000/api/v1/auth/register \\
          -H "Content-Type: application/json" \\
          -d '{"username": "johndoe", "email": "john@example.com"}'

        # 2. Create API key (use user_id from step 1)
        curl -X POST http://localhost:8000/api/v1/auth/create-key \\
          -H "Content-Type: application/json" \\
          -d '{"user_id": "YOUR_USER_ID", "name": "My API Key", "rate_limit": 100}'

        # 3. Use the API
        curl -H "Authorization: Bearer YOUR_API_KEY" \\
          http://localhost:8000/api/v1/books
        ```

        ## Rate Limits

        - Default: 100 requests per hour per API key
        - Configurable during API key creation (max: 100/hour)
        - Rate limit info returned in all responses
        """,
        version="2.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json"
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:8080", "https://yourdomain.com"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API routes
    app.include_router(router, prefix="/api/v1")

    # Health check endpoint
    @app.get("/health", tags=["health"])
    async def health_check():
        """Health check endpoint."""
        try:
            db = get_database()
            # Simple ping to check DB connection
            db.client.admin.command('ping')
            return {
                "status": "healthy",
                "database": "connected"
            }
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "status": "unhealthy",
                    "database": "disconnected",
                    "error": str(e)
                }
            )

    # Root endpoint
    @app.get("/", tags=["root"])
    async def root():
        """Root endpoint with API information."""
        return {
            "message": "Books Crawler API",
            "version": "1.0.0",
            "documentation": "/docs",
            "health": "/health"
        }

    # Exception handler for rate limit cleanup
    @app.middleware("http")
    async def cleanup_middleware(request: Request, call_next):
        """Middleware to periodically cleanup rate limiter."""
        response = await call_next(request)

        # Cleanup old rate limit windows periodically
        import random
        if random.random() < 0.01:  # 1% chance per request
            rate_limiter.cleanup_old_windows()

        return response

    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    from src.utils.config import get_settings

    settings = get_settings()
    uvicorn.run(
        "src.api.app:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload
    )
