"""
ShopSpy - Main Entry Point

FastAPI application for price tracking and notifications.
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from backend.api import router
from backend.config import config
from backend.db import (
    PricesRepository,
    UserStatsRepository,
    get_database,
    init_database,
)
from backend.telegram_bot import telegram_bot
from backend.utils.logging import setup_logging

# Setup logging
log_level = "DEBUG" if config.is_development else "INFO"
json_format = config.is_production
setup_logging(level=log_level, json_format=json_format)

logger = logging.getLogger(__name__)


async def _periodic_cleanup():
    """
    Periodic cleanup task that runs once per day.
    Removes old price records and user statistics.
    """
    while True:
        # Wait first to avoid cleanup on startup
        await asyncio.sleep(config.cleanup.interval_hours * 3600)

        try:
            db = get_database()
            prices_repo = PricesRepository(db)
            user_stats_repo = UserStatsRepository(db)

            deleted_prices = prices_repo.cleanup_old_records(config.cleanup.keep_days)
            deleted_stats = user_stats_repo.cleanup_old_stats(config.cleanup.keep_days)

            if deleted_prices > 0 or deleted_stats > 0:
                logger.info(
                    f"Cleanup completed: removed {deleted_prices} price records, "
                    f"{deleted_stats} user stats records"
                )
        except Exception as e:
            logger.error(f"Cleanup task failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # === STARTUP ===
    logger.info("=" * 50)
    logger.info("ShopSpy starting up...")
    logger.info(f"Environment: {config.env}")
    logger.info(f"Database: {config.database.full_path}")
    logger.info(f"Telegram bot: {'enabled' if config.telegram.enabled else 'disabled'}")
    logger.info(f"AI provider: {config.ai.available_provider or 'not configured'}")
    logger.info("=" * 50)

    # Initialize database
    init_database(config.database.full_path)
    logger.info("Database initialized")

    # Start Telegram bot (in background)
    if config.telegram.enabled:
        asyncio.create_task(telegram_bot.start())
        logger.info("Telegram bot started")

    # Start periodic cleanup task
    asyncio.create_task(_periodic_cleanup())
    logger.info("Periodic cleanup task started")

    yield

    # === SHUTDOWN ===
    logger.info("Shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="ShopSpy API",
    description="AI-powered price tracking for Wildberries and Ozon",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.server.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api")

# Static files (Telegram Mini App)
_static_dir = os.path.join(os.path.dirname(__file__), "static")
_miniapp_dir = os.path.join(_static_dir, "miniapp")
if os.path.isdir(_miniapp_dir):
    app.mount(
        "/miniapp", StaticFiles(directory=_miniapp_dir, html=True), name="miniapp"
    )


# Index page route
@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the landing page."""
    index_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "templates",
        "index.html",
    )

    try:
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return HTMLResponse(
            content="""
            <html>
                <head><title>ShopSpy</title></head>
                <body style="font-family: sans-serif; padding: 40px; background: #0f0f1a; color: #e0e0e0;">
                    <h1>🔍 ShopSpy</h1>
                    <p>Page not found.</p>
                    <p><a href="/docs" style="color: #e94560;">API Documentation</a></p>
                </body>
            </html>
            """,
            status_code=200,
        )


# Dashboard redirect
@app.get("/dashboard")
async def dashboard():
    """Redirect to home page."""
    from fastapi.responses import RedirectResponse

    return RedirectResponse(url="/")


# Health check endpoint (also available at root level)
@app.get("/health")
@app.head("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "environment": config.env,
        "telegram_enabled": config.telegram.enabled,
        "ai_provider": config.ai.available_provider,
    }


# Admin panel route
@app.get("/admin", response_class=HTMLResponse)
async def admin_panel():
    """Serve the admin panel."""
    admin_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "templates",
        "admin.html",
    )

    try:
        with open(admin_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return HTMLResponse(
            content="""
            <html>
                <head><title>ShopSpy Admin</title></head>
                <body style="font-family: sans-serif; padding: 40px; background: #0f0f1a; color: #e0e0e0;">
                    <h1>⚙️ ShopSpy Admin</h1>
                    <p>Admin panel not found. Please ensure templates/admin.html exists.</p>
                    <p><a href="/" style="color: #e94560;">← Back to Dashboard</a></p>
                </body>
            </html>
            """,
            status_code=200,
        )


# Run server
if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting server on {config.server.host}:{config.server.port}")

    uvicorn.run(
        "backend.main:app",
        host=config.server.host,
        port=config.server.port,
        reload=config.is_development,
        log_level="info",
    )
