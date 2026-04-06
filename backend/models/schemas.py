"""
ShopSpy - Pydantic Models / Schemas

Data validation and serialization models for API requests and responses.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

# ─────────────────────────────────────────────────────────────
# Price Models
# ─────────────────────────────────────────────────────────────


class PriceRecord(BaseModel):
    """Request model for recording a price."""

    platform: str = Field(..., description="Platform identifier: 'wb' or 'ozon'")
    product_id: str = Field(..., description="Product ID on the platform")
    product_name: Optional[str] = Field(None, description="Product name")
    price: float = Field(..., gt=0, description="Current price")
    original_price: Optional[float] = Field(
        None, description="Original price before discount"
    )
    url: Optional[str] = Field(None, description="Product URL")

    class Config:
        json_schema_extra = {
            "example": {
                "platform": "wb",
                "product_id": "12345678",
                "product_name": "Wireless Earbuds",
                "price": 1499.0,
                "original_price": 1999.0,
                "url": "https://www.wildberries.ru/catalog/12345678/detail.aspx",
            }
        }


class PriceHistoryItem(BaseModel):
    """Single price history entry."""

    price: float
    original_price: Optional[float] = None
    recorded_at: str


class PriceAnalysis(BaseModel):
    """Price analysis result."""

    verdict: str = Field(
        ...,
        description="good_deal, overpriced, fake_discount, normal, insufficient_data",
    )
    message: str = Field(..., description="Human-readable analysis message")
    current_price: Optional[float] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    avg_price: Optional[float] = None
    claimed_discount: Optional[int] = None
    real_discount_from_max: Optional[int] = None
    real_discount_from_avg: Optional[int] = None


class PriceHistoryResponse(BaseModel):
    """Response model for price history."""

    history: list[PriceHistoryItem]
    analysis: PriceAnalysis


# ─────────────────────────────────────────────────────────────
# Review Models
# ─────────────────────────────────────────────────────────────


class ReviewsAnalyzeRequest(BaseModel):
    """Request model for AI review analysis."""

    platform: str = Field(..., description="Platform identifier")
    product_id: str = Field(..., description="Product ID")
    product_name: str = Field(..., description="Product name for context")
    reviews: list[str] = Field(..., min_length=1, description="List of review texts")

    class Config:
        json_schema_extra = {
            "example": {
                "platform": "wb",
                "product_id": "12345678",
                "product_name": "Wireless Earbuds",
                "reviews": [
                    "Great product! Good sound quality.",
                    "Battery life could be better.",
                    "Fast delivery, recommend!",
                ],
            }
        }


class ReviewSummary(BaseModel):
    """AI-generated review summary."""

    pros: list[str] = Field(default_factory=list, description="Product advantages")
    cons: list[str] = Field(default_factory=list, description="Product disadvantages")
    fake_reviews_detected: bool = Field(
        False, description="Whether fake reviews were detected"
    )
    fake_reviews_reason: Optional[str] = Field(
        None, description="Reason for fake review detection"
    )
    rating_honest: Optional[float] = Field(
        None, ge=1, le=5, description="Honest rating (1-5)"
    )
    verdict: str = Field(..., description="Short verdict")
    buy_recommendation: str = Field(
        "unknown", description="'yes', 'no', 'wait', or 'unknown'"
    )


class ReviewsAnalyzeResponse(BaseModel):
    """Response model for review analysis."""

    summary: ReviewSummary


# ─────────────────────────────────────────────────────────────
# Telegram Models
# ─────────────────────────────────────────────────────────────


class TelegramRegisterRequest(BaseModel):
    """Request model for Telegram registration."""

    chat_id: int = Field(..., description="Telegram Chat ID")
    username: Optional[str] = Field(None, description="Telegram username")


class TelegramStatusResponse(BaseModel):
    """Response model for Telegram status."""

    linked: bool
    is_active: Optional[bool] = None


class TelegramAuthRequest(BaseModel):
    """Request model for Telegram Login Widget authentication."""

    id: int = Field(..., description="Telegram user ID")
    first_name: Optional[str] = Field(None, description="User's first name")
    last_name: Optional[str] = Field(None, description="User's last name")
    username: Optional[str] = Field(None, description="Telegram username")
    photo_url: Optional[str] = Field(None, description="User's profile photo URL")
    hash: str = Field(..., description="Authentication hash from Telegram")

    class Config:
        json_schema_extra = {
            "example": {
                "id": 123456789,
                "first_name": "John",
                "last_name": "Doe",
                "username": "johndoe",
                "photo_url": "https://t.me/i/userpic/320/abc123.jpg",
                "hash": "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            }
        }


class AuthResponse(BaseModel):
    """Response model for authentication."""

    status: str = "ok"
    telegram_id: int
    username: Optional[str] = None
    session_token: Optional[str] = None


class UserInfoResponse(BaseModel):
    """Response model for user info."""

    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    photo_url: Optional[str] = None
    is_active: bool = True
    created_at: Optional[str] = None


# ─────────────────────────────────────────────────────────────
# Alert Models
# ─────────────────────────────────────────────────────────────


class PriceAlertCreate(BaseModel):
    """Request model for creating a price alert."""

    chat_id: int = Field(..., description="Telegram Chat ID")
    platform: str = Field(..., description="Platform identifier")
    product_id: str = Field(..., description="Product ID")
    product_name: Optional[str] = Field(None, description="Product name")
    target_price: Optional[float] = Field(
        None, gt=0, description="Target price for notification"
    )
    url: Optional[str] = Field(None, description="Product URL")

    class Config:
        json_schema_extra = {
            "example": {
                "chat_id": 123456789,
                "platform": "wb",
                "product_id": "12345678",
                "product_name": "Wireless Earbuds",
                "target_price": 1200.0,
                "url": "https://www.wildberries.ru/catalog/12345678/detail.aspx",
            }
        }


class PriceAlertItem(BaseModel):
    """Single price alert item."""

    platform: str
    product_id: str
    product_name: Optional[str] = None
    target_price: Optional[float] = None
    last_price: Optional[float] = None
    url: Optional[str] = None
    created_at: Optional[str] = None


class PriceAlertListResponse(BaseModel):
    """Response model for listing alerts."""

    alerts: list[PriceAlertItem]


# ─────────────────────────────────────────────────────────────
# Stats Models
# ─────────────────────────────────────────────────────────────


class StatsResponse(BaseModel):
    """Response model for statistics."""

    total_records: int
    unique_products: int
    platforms: dict[str, int]
    telegram_users: int
    active_alerts: int


# ─────────────────────────────────────────────────────────────
# Product Models
# ─────────────────────────────────────────────────────────────


class ProductItem(BaseModel):
    """Single product item in list."""

    platform: str
    product_id: str
    name: Optional[str] = None
    url: Optional[str] = None
    min_price: float
    max_price: float
    records: int
    last_seen: Optional[str] = None


class ProductListResponse(BaseModel):
    """Response model for product list."""

    products: list[ProductItem]


# ─────────────────────────────────────────────────────────────
# Common Response Models
# ─────────────────────────────────────────────────────────────


class SuccessResponse(BaseModel):
    """Generic success response."""

    status: str = "ok"
    message: Optional[str] = None


class ErrorResponse(BaseModel):
    """Generic error response."""

    status: str = "error"
    message: str
    detail: Optional[str] = None
