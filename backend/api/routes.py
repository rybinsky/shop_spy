"""
ShopSpy - API Routes

FastAPI routes for price tracking, alerts, and AI analysis.
"""

import hashlib
import hmac
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from backend.config import config
from backend.db import AlertsRepository, PricesRepository, UsersRepository, get_database
from backend.models.schemas import (
    AuthResponse,
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
    TelegramAuthRequest,
    TelegramRegisterRequest,
    TelegramStatusResponse,
    UserInfoResponse,
)
from backend.services.ai_analyzer import AIAnalyzer
from backend.services.price_analyzer import PriceAnalyzer

logger = logging.getLogger(__name__)

# Create routers
api_router = APIRouter()

# Services
price_analyzer = PriceAnalyzer()
ai_analyzer = AIAnalyzer()

# Rate limiting state
_rate_data: dict = {}
_global_rate: dict = {"count": 0, "date": None}


# ─────────────────────────────────────────────────────────────
# Dependencies
# ─────────────────────────────────────────────────────────────


def get_prices_repo() -> PricesRepository:
    """Get prices repository."""
    return PricesRepository(get_database())


def get_users_repo() -> UsersRepository:
    """Get users repository."""
    return UsersRepository(get_database())


def get_alerts_repo() -> AlertsRepository:
    """Get alerts repository."""
    return AlertsRepository(get_database())


def check_rate_limit(request: Request) -> None:
    """
    Check rate limiting for AI requests.

    Args:
        request: FastAPI request object

    Raises:
        HTTPException: If rate limit exceeded
    """
    from datetime import datetime

    ip = request.client.host if request.client else "unknown"
    today = datetime.now().date().isoformat()

    # Check global limit
    if _global_rate["date"] != today:
        _global_rate["count"] = 0
        _global_rate["date"] = today

    if _global_rate["count"] >= config.ai.rate_limit_global:
        raise HTTPException(
            status_code=429,
            detail="Глобальный дневной лимит AI-запросов исчерпан. Попробуйте завтра.",
        )

    # Check per-IP limit
    entry = _rate_data.get(ip)
    if not entry or entry["date"] != today:
        _rate_data[ip] = {"count": 0, "date": today}
        entry = _rate_data[ip]

    if entry["count"] >= config.ai.rate_limit_per_ip:
        raise HTTPException(
            status_code=429,
            detail=f"Лимит {config.ai.rate_limit_per_ip} AI-запросов в день с вашего IP исчерпан.",
        )

    entry["count"] += 1
    _global_rate["count"] += 1


# ─────────────────────────────────────────────────────────────
# Telegram Auth Helpers
# ─────────────────────────────────────────────────────────────


def verify_telegram_auth(auth_data: dict, bot_token: str) -> bool:
    """
    Verify Telegram Login Widget authentication hash.

    Args:
        auth_data: Dictionary with Telegram auth data (including 'hash')
        bot_token: Telegram bot token

    Returns:
        True if hash is valid, False otherwise
    """
    # 1. Remove hash from data
    data = {k: v for k, v in auth_data.items() if k != "hash" and v is not None}

    # 2. Sort keys and create data_check_string
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))

    # 3. Create secret_key = SHA256(bot_token)
    secret_key = hashlib.sha256(bot_token.encode()).digest()

    # 4. Compute hash = HMAC_SHA256(secret_key, data_check_string)
    computed_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    # 5. Compare
    return computed_hash == auth_data["hash"]


# ─────────────────────────────────────────────────────────────
# Price Routes
# ─────────────────────────────────────────────────────────────


@api_router.post(
    "/price", response_model=SuccessResponse, responses={400: {"model": ErrorResponse}}
)
def record_price(
    record: PriceRecord,
    prices: PricesRepository = Depends(get_prices_repo),
):
    """Record a price from the browser extension."""
    try:
        saved, old_price = prices.record_price(
            platform=record.platform,
            product_id=record.product_id,
            price=record.price,
            product_name=record.product_name,
            original_price=record.original_price,
            url=record.url,
        )

        if saved:
            return SuccessResponse(status="ok", message="Цена записана")
        return SuccessResponse(status="skipped", message="Цена не изменилась")

    except Exception as e:
        logger.error(f"Failed to record price: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/price/history", response_model=PriceHistoryResponse)
def get_price_history(
    platform: str,
    product_id: str,
    limit: int = Query(default=30, ge=1, le=100),
    prices: PricesRepository = Depends(get_prices_repo),
):
    """Get price history for a product."""
    history = prices.get_price_history(platform, product_id, limit)
    analysis = price_analyzer.analyze(history)

    return PriceHistoryResponse(
        history=[PriceHistoryItem(**h) for h in history],
        analysis=PriceAnalysis(**analysis),
    )


# ─────────────────────────────────────────────────────────────
# AI Analysis Routes
# ─────────────────────────────────────────────────────────────


@api_router.post("/reviews/analyze", response_model=ReviewsAnalyzeResponse)
async def analyze_reviews(
    request: Request,
    data: ReviewsAnalyzeRequest,
    prices: PricesRepository = Depends(get_prices_repo),
):
    """Analyze product reviews using AI."""
    # Check rate limit
    check_rate_limit(request)

    # Check cache first
    db = get_database()
    with db.get_connection() as conn:
        cached = conn.execute(
            """SELECT summary FROM reviews_cache
               WHERE platform = ? AND product_id = ?
               ORDER BY created_at DESC LIMIT 1""",
            (data.platform, data.product_id),
        ).fetchone()

        if cached and cached["summary"]:
            try:
                import json

                summary = json.loads(cached["summary"])
                logger.debug(
                    f"Returning cached analysis for {data.platform}:{data.product_id}"
                )
                return ReviewsAnalyzeResponse(summary=ReviewSummary(**summary))
            except (json.JSONDecodeError, KeyError, TypeError):
                pass

    # Analyze with AI
    result = await ai_analyzer.analyze_reviews(data.product_name, data.reviews)

    # Cache result
    import json

    with db.get_connection() as conn:
        conn.execute(
            """INSERT INTO reviews_cache (platform, product_id, summary)
               VALUES (?, ?, ?)""",
            (data.platform, data.product_id, json.dumps(result, ensure_ascii=False)),
        )

    return ReviewsAnalyzeResponse(summary=ReviewSummary(**result))


# ─────────────────────────────────────────────────────────────
# Telegram Routes
# ─────────────────────────────────────────────────────────────


@api_router.post("/telegram/register", response_model=SuccessResponse)
def register_telegram(
    data: TelegramRegisterRequest,
    users: UsersRepository = Depends(get_users_repo),
):
    """Register a Telegram user for notifications."""
    if not config.telegram.enabled:
        return SuccessResponse(
            status="error",
            message="Telegram бот не настроен. Установите TELEGRAM_BOT_TOKEN.",
        )

    success = users.save_user(data.chat_id, data.username)

    if success:
        return SuccessResponse(status="ok", message="Telegram привязан успешно")
    return SuccessResponse(status="error", message="Ошибка при сохранении")


@api_router.get("/telegram/status", response_model=TelegramStatusResponse)
def telegram_status(
    chat_id: int,
    users: UsersRepository = Depends(get_users_repo),
):
    """Check Telegram registration status."""
    user = users.get_user(chat_id)

    if user:
        return TelegramStatusResponse(
            linked=True, is_active=user.get("is_active", False)
        )
    return TelegramStatusResponse(linked=False)


# ─────────────────────────────────────────────────────────────
# Auth Routes (Telegram Login Widget)
# ─────────────────────────────────────────────────────────────


@api_router.post("/auth/telegram", response_model=AuthResponse)
def telegram_auth(
    data: TelegramAuthRequest,
    users: UsersRepository = Depends(get_users_repo),
):
    """
    Authenticate user via Telegram Login Widget.

    Validates the hash from Telegram and creates/updates the user.
    Returns a session token (telegram_id).
    """
    if not config.telegram.enabled or not config.telegram.bot_token:
        logger.warning("Telegram auth attempted but bot not configured")
        raise HTTPException(
            status_code=503,
            detail="Telegram авторизация не настроена",
        )

    # Prepare auth data for verification
    auth_data = {
        "id": data.id,
        "first_name": data.first_name,
        "last_name": data.last_name,
        "username": data.username,
        "photo_url": data.photo_url,
        "hash": data.hash,
    }

    # Verify hash
    if not verify_telegram_auth(auth_data, config.telegram.bot_token):
        logger.warning(f"Invalid Telegram auth hash for user {data.id}")
        raise HTTPException(
            status_code=401,
            detail="Неверная подпись Telegram",
        )

    logger.info(f"Telegram auth verified for user {data.id}")

    # Save/update user
    success = users.save_user_from_telegram_auth(
        telegram_id=data.id,
        first_name=data.first_name,
        last_name=data.last_name,
        username=data.username,
        photo_url=data.photo_url,
    )

    if not success:
        raise HTTPException(
            status_code=500,
            detail="Ошибка при сохранении пользователя",
        )

    return AuthResponse(
        status="ok",
        telegram_id=data.id,
        username=data.username,
        session_token=str(data.id),  # Simple session token = telegram_id
    )


@api_router.get("/auth/me", response_model=UserInfoResponse)
def get_current_user(
    telegram_id: int = Query(..., description="Telegram user ID"),
    users: UsersRepository = Depends(get_users_repo),
):
    """
    Get current authenticated user info.

    Uses telegram_id from query parameter for authentication.
    """
    user = users.get_user_by_telegram_id(telegram_id)

    if not user:
        raise HTTPException(
            status_code=404,
            detail="Пользователь не найден",
        )

    return UserInfoResponse(
        telegram_id=user["chat_id"],
        username=user.get("username"),
        first_name=user.get("first_name"),
        last_name=user.get("last_name"),
        photo_url=user.get("photo_url"),
        is_active=bool(user.get("is_active", True)),
        created_at=str(user.get("created_at")) if user.get("created_at") else None,
    )


# ─────────────────────────────────────────────────────────────
# Alerts Routes
# ─────────────────────────────────────────────────────────────


@api_router.post("/alerts", response_model=SuccessResponse)
def create_alert(
    data: PriceAlertCreate,
    alerts: AlertsRepository = Depends(get_alerts_repo),
):
    """Create a price alert."""
    success = alerts.create_alert(
        chat_id=data.chat_id,
        platform=data.platform,
        product_id=data.product_id,
        product_name=data.product_name,
        target_price=data.target_price,
        url=data.url,
    )

    if success:
        return SuccessResponse(status="ok", message="Уведомление создано")
    return SuccessResponse(status="error", message="Ошибка при создании")


@api_router.get("/alerts", response_model=PriceAlertListResponse)
def get_alerts(
    chat_id: int,
    alerts: AlertsRepository = Depends(get_alerts_repo),
):
    """Get all alerts for a user."""
    alert_list = alerts.get_alerts_by_chat(chat_id)
    return PriceAlertListResponse(alerts=[PriceAlertItem(**a) for a in alert_list])


@api_router.delete("/alerts", response_model=SuccessResponse)
def delete_alert(
    chat_id: int,
    platform: str,
    product_id: str,
    alerts: AlertsRepository = Depends(get_alerts_repo),
):
    """Delete a price alert."""
    success = alerts.delete_alert(chat_id, platform, product_id)

    if success:
        return SuccessResponse(status="ok", message="Уведомление удалено")
    return SuccessResponse(status="error", message="Ошибка при удалении")


# ─────────────────────────────────────────────────────────────
# Stats & Products Routes
# ─────────────────────────────────────────────────────────────


@api_router.get("/stats", response_model=StatsResponse)
def get_stats(
    prices: PricesRepository = Depends(get_prices_repo),
    users: UsersRepository = Depends(get_users_repo),
    alerts: AlertsRepository = Depends(get_alerts_repo),
):
    """Get application statistics."""
    price_stats = prices.get_stats()
    telegram_users = users.count_active_users()
    active_alerts = alerts.count_active_alerts()

    return StatsResponse(
        total_records=price_stats["total_records"],
        unique_products=price_stats["unique_products"],
        platforms=price_stats["platforms"],
        telegram_users=telegram_users,
        active_alerts=active_alerts,
    )


@api_router.get("/products", response_model=ProductListResponse)
def get_products(
    limit: int = Query(default=50, ge=1, le=200),
    prices: PricesRepository = Depends(get_prices_repo),
):
    """Get list of tracked products."""
    products = prices.get_tracked_products(limit)
    return ProductListResponse(products=[ProductItem(**p) for p in products])


# ─────────────────────────────────────────────────────────────
# Utility Routes
# ─────────────────────────────────────────────────────────────


@api_router.post("/crawl")
def trigger_crawl():
    """Manually trigger price crawl (for testing)."""
    from backend.services.crawler import crawler

    crawler.run_once_sync()
    return SuccessResponse(status="ok", message="Обход запущен")


@api_router.get("/health")
def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "telegram_enabled": config.telegram.enabled,
        "ai_provider": ai_analyzer.provider,
    }


# ─────────────────────────────────────────────────────────────
# Admin API (Developer Panel)
# ─────────────────────────────────────────────────────────────


@api_router.get("/admin/users")
def admin_get_users(
    users: UsersRepository = Depends(get_users_repo),
):
    """Get all registered users (admin)."""
    all_users = users.get_all_users()
    return {"users": all_users}


@api_router.get("/admin/alerts")
def admin_get_all_alerts(
    alerts: AlertsRepository = Depends(get_alerts_repo),
):
    """Get all alerts (admin)."""
    all_alerts = alerts.get_all_alerts()
    return {"alerts": all_alerts}


@api_router.get("/admin/stats")
def admin_get_detailed_stats(
    prices: PricesRepository = Depends(get_prices_repo),
    users: UsersRepository = Depends(get_users_repo),
    alerts: AlertsRepository = Depends(get_alerts_repo),
):
    """Get detailed statistics (admin)."""
    price_stats = prices.get_stats()

    # Recent activity
    recent_prices = prices.get_recent_prices(20)
    recent_alerts = alerts.get_recent_alerts(20)

    return {
        "overview": {
            "total_records": price_stats["total_records"],
            "unique_products": price_stats["unique_products"],
            "platforms": price_stats["platforms"],
            "telegram_users": users.count_active_users(),
            "active_alerts": alerts.count_active_alerts(),
        },
        "recent_prices": recent_prices,
        "recent_alerts": recent_alerts,
        "config": {
            "crawler_interval_hours": config.crawler.interval_seconds // 3600,
            "ai_provider": ai_analyzer.provider,
            "telegram_enabled": config.telegram.enabled,
        },
    }
