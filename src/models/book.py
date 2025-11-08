"""Pydantic models for Book data."""
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field, HttpUrl, field_validator
from bson import ObjectId


class PyObjectId(ObjectId):
    """Custom ObjectId type for Pydantic."""

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, field_schema):
        field_schema.update(type="string")


class Book(BaseModel):
    """Book model with all required fields."""

    name: str = Field(..., description="Name of the book", min_length=1)
    description: str = Field(..., description="Description of the book")
    category: str = Field(..., description="Book category")
    price_including_tax: float = Field(..., description="Price including tax", gt=0)
    price_excluding_tax: float = Field(..., description="Price excluding tax", gt=0)
    availability: str = Field(..., description="Availability status")
    number_of_reviews: int = Field(..., description="Number of reviews", ge=0)
    image_url: str = Field(..., description="URL of the book cover image")
    rating: int = Field(..., description="Rating (1-5)", ge=1, le=5)
    source_url: str = Field(..., description="Source URL of the book page")

    @field_validator('rating')
    @classmethod
    def validate_rating(cls, v):
        if v not in range(1, 6):
            raise ValueError('Rating must be between 1 and 5')
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "name": "A Light in the Attic",
                "description": "A collection of poems and drawings by Shel Silverstein",
                "category": "Poetry",
                "price_including_tax": 51.77,
                "price_excluding_tax": 51.77,
                "availability": "In stock (22 available)",
                "number_of_reviews": 0,
                "image_url": "https://books.toscrape.com/media/cache/2c/da/2cdad67c44b002e7ead0cc35693c0e8b.jpg",
                "rating": 3,
                "source_url": "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html"
            }
        }


class BookInDB(Book):
    """Book model as stored in database with metadata."""

    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    crawl_timestamp: datetime = Field(default_factory=datetime.now)
    last_updated: datetime = Field(default_factory=datetime.now)
    status: str = Field(default="active", description="Crawl status")
    content_hash: str = Field(..., description="Hash of content for change detection")
    html_snapshot_path: Optional[str] = Field(None, description="Path to HTML snapshot")

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
        json_schema_extra = {
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "name": "A Light in the Attic",
                "description": "A collection of poems",
                "category": "Poetry",
                "price_including_tax": 51.77,
                "price_excluding_tax": 51.77,
                "availability": "In stock",
                "number_of_reviews": 0,
                "image_url": "https://books.toscrape.com/media/cache/image.jpg",
                "rating": 3,
                "source_url": "https://books.toscrape.com/catalogue/book/index.html",
                "crawl_timestamp": "2024-01-01T00:00:00",
                "last_updated": "2024-01-01T00:00:00",
                "status": "active",
                "content_hash": "abc123def456",
                "html_snapshot_path": "html_snapshots/book_123.html"
            }
        }


class BookChange(BaseModel):
    """Model for tracking book changes."""

    book_id: str = Field(..., description="Book ID")
    book_name: str = Field(..., description="Book name for reference")
    change_type: str = Field(..., description="Type of change: new, updated, deleted")
    changed_fields: dict = Field(default_factory=dict, description="Fields that changed with old/new values")
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp of the change")

    class Config:
        json_schema_extra = {
            "example": {
                "book_id": "507f1f77bcf86cd799439011",
                "book_name": "A Light in the Attic",
                "change_type": "updated",
                "changed_fields": {
                    "price_including_tax": {"old": 51.77, "new": 49.99},
                    "availability": {"old": "In stock (22 available)", "new": "In stock (15 available)"}
                },
                "timestamp": "2024-01-01T12:00:00"
            }
        }


class CrawlState(BaseModel):
    """Model for storing crawler state for resumability."""

    last_successful_url: Optional[str] = None
    last_crawl_time: Optional[datetime] = None
    total_books_crawled: int = 0
    status: str = "idle"  # idle, running, completed, failed
    error_message: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "last_successful_url": "https://books.toscrape.com/catalogue/page-5.html",
                "last_crawl_time": "2024-01-01T00:00:00",
                "total_books_crawled": 120,
                "status": "running",
                "error_message": None
            }
        }
