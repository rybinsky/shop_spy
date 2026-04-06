"""
ShopSpy - Data Models

Pydantic models for API request/response validation.
"""

from backend.models.schemas import (
    ErrorResponse,
    PriceAlertCreate,
    PriceAlertItem,
    PriceAlertListResponse,
    PriceAnalysis,
    PriceHistoryItem,
    PriceHistoryResponse,
    PriceRecord,
    ProductItem,
    ProductListResponse,
    ReviewsAnalyzeRequest,
    ReviewsAnalyzeResponse,
    ReviewSummary,
    StatsResponse,
    SuccessResponse,
    TelegramRegisterRequest,
    TelegramStatusResponse,
)

__all__ = [
    "PriceRecord",
    "PriceHistoryItem",
    "PriceHistoryResponse",
    "PriceAnalysis",
    "ReviewsAnalyzeRequest",
    "ReviewsAnalyzeResponse",
    "ReviewSummary",
    "TelegramRegisterRequest",
    "TelegramStatusResponse",
    "PriceAlertCreate",
    "PriceAlertItem",
    "PriceAlertListResponse",
    "ProductItem",
    "ProductListResponse",
    "StatsResponse",
    "SuccessResponse",
    "ErrorResponse",
]
