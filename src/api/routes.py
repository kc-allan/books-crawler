"""API routes for book endpoints."""
from typing import List, Optional
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Query, HTTPException, status, Body
from pydantic import BaseModel, EmailStr, Field
from bson import ObjectId
from src.utils.database import get_database, Database
from src.utils.logger import get_logger
from src.models.user import APIKey, RateLimitInfo, User
from src.models.book import BookChange
from .auth import auth_manager
from .rate_limiter import rate_limiter

logger = get_logger()

router = APIRouter()


# Request/Response models for auth endpoints
class CreateUserRequest(BaseModel):
    """Request model for creating a user."""
    username: str = Field(..., min_length=3, max_length=50, description="Username")
    email: EmailStr = Field(..., description="Email address")

    class Config:
        json_schema_extra = {
            "example": {
                "username": "johndoe",
                "email": "john@example.com"
            }
        }


class CreateUserResponse(BaseModel):
    """Response model for user creation."""
    user_id: str
    username: str
    email: str
    message: str


class CreateAPIKeyRequest(BaseModel):
    """Request model for creating an API key."""
    user_id: str = Field(..., description="User ID")
    name: str = Field(..., min_length=1, max_length=100, description="API key name")
    rate_limit: int = Field(default=100, ge=1, le=10000, description="Requests per hour")

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "507f1f77bcf86cd799439011",
                "name": "Production API Key",
                "rate_limit": 100
            }
        }


class CreateAPIKeyResponse(BaseModel):
    """Response model for API key creation."""
    api_key: str
    name: str
    user_id: str
    rate_limit: int
    message: str

    class Config:
        json_schema_extra = {
            "example": {
                "api_key": "sk_live_abc123...",
                "name": "Production API Key",
                "user_id": "507f1f77bcf86cd799439011",
                "rate_limit": 100,
                "message": "API key created successfully. Keep this key secure!"
            }
        }


# Response models
class BookResponse(BaseModel):
    """Book response model."""
    id: str
    name: str
    description: str
    category: str
    price_including_tax: float
    price_excluding_tax: float
    availability: str
    number_of_reviews: int
    image_url: str
    rating: int
    source_url: str
    last_updated: str

    class Config:
        json_schema_extra = {
            "example": {
                "id": "507f1f77bcf86cd799439011",
                "name": "A Light in the Attic",
                "description": "A collection of poems",
                "category": "Poetry",
                "price_including_tax": 51.77,
                "price_excluding_tax": 51.77,
                "availability": "In stock (22 available)",
                "number_of_reviews": 0,
                "image_url": "https://books.toscrape.com/media/cache/image.jpg",
                "rating": 3,
                "source_url": "https://books.toscrape.com/catalogue/book/index.html",
                "last_updated": "2024-01-01T12:00:00"
            }
        }


class PaginatedBooksResponse(BaseModel):
    """Paginated books response."""
    total: int
    page: int
    page_size: int
    total_pages: int
    books: List[BookResponse]
    rate_limit_info: Optional[RateLimitInfo] = None


class ChangeResponse(BaseModel):
    """Change response model."""
    book_id: str
    book_name: str
    change_type: str
    changed_fields: dict
    timestamp: str


class PaginatedChangesResponse(BaseModel):
    """Paginated changes response."""
    total: int
    page: int
    page_size: int
    total_pages: int
    changes: List[ChangeResponse]
    rate_limit_info: Optional[RateLimitInfo] = None


def format_book(book_doc: dict) -> BookResponse:
    """Convert MongoDB document to BookResponse."""
    return BookResponse(
        id=str(book_doc['_id']),
        name=book_doc['name'],
        description=book_doc['description'],
        category=book_doc['category'],
        price_including_tax=book_doc['price_including_tax'],
        price_excluding_tax=book_doc['price_excluding_tax'],
        availability=book_doc['availability'],
        number_of_reviews=book_doc['number_of_reviews'],
        image_url=book_doc['image_url'],
        rating=book_doc['rating'],
        source_url=book_doc['source_url'],
        last_updated=book_doc['last_updated'].isoformat() if isinstance(book_doc.get('last_updated'), datetime) else str(book_doc.get('last_updated', ''))
    )


# ============================================================================
# Authentication Endpoints
# ============================================================================

@router.post("/auth/register", response_model=CreateUserResponse, status_code=status.HTTP_201_CREATED, tags=["authentication"])
async def register_user(request: CreateUserRequest):
    """
    Register a new user.

    Create a new user account. This is the first step before creating API keys.
    No authentication required for user registration.

    - **username**: Unique username (3-50 characters)
    - **email**: Valid email address (must be unique)

    Returns the created user ID which can be used to generate API keys.
    """
    try:
        db = get_database()
        users_collection = db.get_collection('users')

        # Check if username already exists
        if users_collection.find_one({'username': request.username}):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Username '{request.username}' already exists"
            )

        # Check if email already exists
        if users_collection.find_one({'email': request.email}):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Email '{request.email}' already registered"
            )

        # Create user
        user_id = auth_manager.create_user(request.username, request.email)

        return CreateUserResponse(
            user_id=user_id,
            username=request.username,
            email=request.email,
            message=f"User '{request.username}' created successfully. Use the user_id to create API keys."
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating user"
        )


@router.post("/auth/create-key", response_model=CreateAPIKeyResponse, status_code=status.HTTP_201_CREATED, tags=["authentication"])
async def create_api_key(request: CreateAPIKeyRequest):
    """
    Create a new API key for a user.

    Generate a new Bearer token (API key) for an existing user.
    No authentication required for API key creation.

    - **user_id**: The user ID from registration
    - **name**: Descriptive name for the key (e.g., "Production Key", "Development Key")
    - **rate_limit**: Maximum requests per hour (default: 100, max: 10000)

    Returns the API key which should be used as a Bearer token in subsequent requests.

    **IMPORTANT**: Save this key securely! It won't be shown again.
    """
    try:
        db = get_database()
        users_collection = db.get_collection('users')

        # Verify user exists
        if not ObjectId.is_valid(request.user_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user ID format"
            )

        user = users_collection.find_one({'_id': ObjectId(request.user_id)})
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID '{request.user_id}' not found"
            )

        # Create API key
        api_key = auth_manager.create_api_key(
            user_id=request.user_id,
            name=request.name,
            rate_limit=request.rate_limit,
            rate_period=3600  # 1 hour
        )

        return CreateAPIKeyResponse(
            api_key=api_key.key,
            name=api_key.name,
            user_id=api_key.user_id,
            rate_limit=api_key.rate_limit,
            message="API key created successfully. Keep this key secure! Use it as: Authorization: Bearer <your-key>"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating API key: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating API key"
        )


# ============================================================================
# Book Endpoints
# ============================================================================

@router.get("/books", response_model=PaginatedBooksResponse, tags=["books"])
async def get_books(
    category: Optional[str] = Query(None, description="Filter by category"),
    min_price: Optional[float] = Query(None, ge=0, description="Minimum price"),
    max_price: Optional[float] = Query(None, ge=0, description="Maximum price"),
    rating: Optional[int] = Query(None, ge=1, le=5, description="Filter by rating"),
    sort_by: Optional[str] = Query("rating", regex="^(rating|price|reviews)$", description="Sort field"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    api_key: APIKey = Depends(auth_manager.verify_token),
    db: Database = Depends(get_database)
):
    """
    Get books with filtering, sorting, and pagination.

    Requires Bearer token authentication.

    - **category**: Filter by book category
    - **min_price**: Minimum price filter
    - **max_price**: Maximum price filter
    - **rating**: Filter by rating (1-5)
    - **sort_by**: Sort by rating, price, or reviews
    - **page**: Page number (starting from 1)
    - **page_size**: Number of items per page (max 100)
    """
    try:
        # Check rate limit
        rate_limit_info = rate_limiter.check_rate_limit(api_key)

        books_collection = db.get_collection('books')

        # Build query filter
        query = {'status': 'active'}

        if category:
            query['category'] = {'$regex': category, '$options': 'i'}

        if min_price is not None or max_price is not None:
            price_filter = {}
            if min_price is not None:
                price_filter['$gte'] = min_price
            if max_price is not None:
                price_filter['$lte'] = max_price
            query['price_including_tax'] = price_filter

        if rating is not None:
            query['rating'] = rating

        # Count total matching documents
        total = books_collection.count_documents(query)

        # Build sort criteria
        sort_field_map = {
            'rating': 'rating',
            'price': 'price_including_tax',
            'reviews': 'number_of_reviews'
        }
        sort_field = sort_field_map.get(sort_by, 'rating')
        sort_direction = -1  # Descending

        # Calculate pagination
        skip = (page - 1) * page_size
        total_pages = (total + page_size - 1) // page_size

        # Fetch books
        cursor = books_collection.find(query).sort(sort_field, sort_direction).skip(skip).limit(page_size)
        books = [format_book(book) for book in cursor]

        return PaginatedBooksResponse(
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            books=books,
            rate_limit_info=rate_limit_info
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching books: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching books"
        )


@router.get("/books/{book_id}", response_model=BookResponse, tags=["books"])
async def get_book_by_id(
    book_id: str,
    api_key: APIKey = Depends(auth_manager.verify_token),
    db: Database = Depends(get_database)
):
    """
    Get a specific book by ID.

    Requires Bearer token authentication.

    - **book_id**: MongoDB ObjectId of the book
    """
    try:
        # Check rate limit
        rate_limiter.check_rate_limit(api_key)

        # Validate ObjectId
        if not ObjectId.is_valid(book_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid book ID format"
            )

        books_collection = db.get_collection('books')

        # Find book
        book = books_collection.find_one({'_id': ObjectId(book_id)})

        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found"
            )

        return format_book(book)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching book {book_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching book"
        )


@router.get("/changes", response_model=PaginatedChangesResponse, tags=["changes"])
async def get_changes(
    change_type: Optional[str] = Query(None, regex="^(new|updated|deleted)$", description="Filter by change type"),
    days: int = Query(7, ge=1, le=90, description="Number of days to look back"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
    api_key: APIKey = Depends(auth_manager.verify_token),
    db: Database = Depends(get_database)
):
    """
    Get recent book changes.

    Requires Bearer token authentication.

    - **change_type**: Filter by type (new, updated, deleted)
    - **days**: Number of days to look back (1-90)
    - **page**: Page number (starting from 1)
    - **page_size**: Number of items per page (max 200)
    """
    try:
        # Check rate limit
        rate_limit_info = rate_limiter.check_rate_limit(api_key)

        changes_collection = db.get_collection('changes')

        # Build query filter
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        query = {'timestamp': {'$gte': cutoff_date}}

        if change_type:
            query['change_type'] = change_type

        # Count total matching documents
        total = changes_collection.count_documents(query)

        # Calculate pagination
        skip = (page - 1) * page_size
        total_pages = (total + page_size - 1) // page_size

        # Fetch changes
        cursor = changes_collection.find(query, {'_id': 0}).sort('timestamp', -1).skip(skip).limit(page_size)

        changes = []
        for change in cursor:
            changes.append(ChangeResponse(
                book_id=change['book_id'],
                book_name=change['book_name'],
                change_type=change['change_type'],
                changed_fields=change.get('changed_fields', {}),
                timestamp=change['timestamp'].isoformat() if isinstance(change.get('timestamp'), datetime) else str(change.get('timestamp', ''))
            ))

        return PaginatedChangesResponse(
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            changes=changes,
            rate_limit_info=rate_limit_info
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching changes: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching changes"
        )
