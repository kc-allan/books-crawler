"""Pydantic models for User and API Key management."""
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field, EmailStr
from bson import ObjectId


class User(BaseModel):
    """User model for API key association."""

    id: Optional[str] = Field(default=None, alias="_id")
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.now)

    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}


class APIKey(BaseModel):
    """API Key model with rate limiting metadata."""

    id: Optional[str] = Field(default=None, alias="_id")
    key: str = Field(..., description="The API key")
    user_id: str = Field(..., description="Associated user ID")
    name: str = Field(..., description="Friendly name for the key")
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.now)
    last_used: Optional[datetime] = None
    request_count: int = Field(default=0, description="Total requests made")
    rate_limit: int = Field(default=100, description="Requests allowed per period")
    rate_period: int = Field(default=3600, description="Period in seconds")

    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}
        json_schema_extra = {
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "key": "sk_live_abc123def456",
                "user_id": "507f1f77bcf86cd799439012",
                "name": "Production API Key",
                "is_active": True,
                "created_at": "2024-01-01T00:00:00",
                "last_used": "2024-01-01T12:00:00",
                "request_count": 1500,
                "rate_limit": 100,
                "rate_period": 3600
            }
        }


class RateLimitInfo(BaseModel):
    """Rate limit information for API responses."""

    remaining: int
    limit: int
    reset_time: datetime
