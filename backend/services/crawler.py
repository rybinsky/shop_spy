"""
ShopSpy - Crawler Service

Background service for periodically checking prices and sending notifications.
"""

import asyncio
import logging
from typing import Optional

import httpx

from backend.config import config
from backend.db import AlertsRepository, PricesRepository, get_database
from backend.services.price_analyzer import PriceAnalyzer
from backend.utils.marketplace_api import MarketplaceAPI

logger = logging.getLogger(__name__)


class CrawlerService:
    """Service for crawling prices and sending notifications."""

    def __init__(self):
        """Initialize crawler service."""
        self.marketplace_api = MarketplaceAPI(
            timeout=config.crawler.timeout,
            max_retries=config.crawler.max_retries,
        )
        self.price_analyzer = PriceAnalyzer()
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the crawler background task."""
        if self._running:
            logger.warning("Crawler is already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._crawl_loop())
        logger.info(
            f"Crawler started. Interval: {config.crawler.interval_seconds // 3600} hours"
        )

    async def stop(self) -> None:
        """Stop the crawler."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Crawler stopped")

    async def _crawl_loop(self) -> None:
        """Main crawler loop with proper cancellation handling."""
        # Initial delay to let the server start
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            return

        while self._running:
            try:
                await self.crawl_once()
            except asyncio.CancelledError:
                logger.info("Crawler cancelled")
                return
            except Exception as e:
                logger.error(f"Crawl iteration failed: {e}")

            if not self._running:
                break

            # Sleep with periodic checks for shutdown
            logger.info(
                f"Next crawl in {config.crawler.interval_seconds // 3600} hours"
            )

            # Sleep in small intervals to check for shutdown
            sleep_remaining = config.crawler.interval_seconds
            while sleep_remaining > 0 and self._running:
                sleep_time = min(60, sleep_remaining)  # Check every minute
                try:
                    await asyncio.sleep(sleep_time)
                except asyncio.CancelledError:
                    return
                sleep_remaining -= sleep_time

    async def crawl_once(self) -> dict:
        """
        Perform a single crawl of all tracked products.

        Returns:
            Dictionary with crawl statistics
        """
        db = get_database()
        prices_repo = PricesRepository(db)
        alerts_repo = AlertsRepository(db)

        # Get products to crawl
        products = prices_repo.get_products_for_crawl()

        if not products:
            logger.debug("No products to crawl")
            return {"checked": 0, "updated": 0, "notifications": 0, "errors": 0}

        stats = {
            "checked": 0,
            "updated": 0,
            "notifications": 0,
            "errors": 0,
        }

        logger.info(f"Starting crawl of {len(products)} products")

        async with httpx.AsyncClient(
            headers=self.marketplace_api.default_headers,
            follow_redirects=True,
            timeout=config.crawler.timeout,
        ) as client:
            for product in products:
                if not self._running:  # Check for shutdown
                    break

                try:
                    result = await self._crawl_product(
                        client=client,
                        product=product,
                        prices_repo=prices_repo,
                        alerts_repo=alerts_repo,
                    )

                    stats["checked"] += 1
                    if result.get("updated"):
                        stats["updated"] += 1
                    if result.get("notified"):
                        stats["notifications"] += 1

                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    stats["errors"] += 1
                    logger.error(
                        f"Error crawling {product['platform']}:{product['product_id']}: {e}"
                    )

                # Delay between requests to avoid rate limiting
                try:
                    await asyncio.sleep(config.crawler.request_delay)
                except asyncio.CancelledError:
                    raise

        logger.info(
            f"Crawl completed: checked={stats['checked']}, "
            f"updated={stats['updated']}, "
            f"notifications={stats['notifications']}, "
            f"errors={stats['errors']}"
        )

        return stats

    async def _crawl_product(
        self,
        client: httpx.AsyncClient,
        product: dict,
        prices_repo: PricesRepository,
        alerts_repo: AlertsRepository,
    ) -> dict:
        """
        Crawl a single product.

        Args:
            client: HTTP client
            product: Product dict with platform, product_id, product_name, url
            prices_repo: Prices repository
            alerts_repo: Alerts repository

        Returns:
            Dict with 'updated' and 'notified' flags
        """
        result = {"updated": False, "notified": False}

        platform = product["platform"]
        product_id = product["product_id"]

        # Fetch current price
        price_data = await self.marketplace_api.fetch_price(
            client, platform, product_id
        )

        if not price_data or price_data.get("price", 0) <= 0:
            logger.debug(f"No valid price for {platform}:{product_id}")
            return result

        new_price = price_data["price"]
        product_name = price_data.get("name") or product.get("product_name", "")

        # Get old price before saving
        old_price = prices_repo.get_last_price(platform, product_id)

        # Save new price
        saved, _ = prices_repo.record_price(
            platform=platform,
            product_id=product_id,
            price=new_price,
            product_name=product_name,
            original_price=price_data.get("original_price"),
            url=product.get("url"),
        )

        result["updated"] = saved

        # Send notifications if price changed
        if saved and old_price and new_price != old_price:
            notified = await self._send_notifications(
                platform=platform,
                product_id=product_id,
                product_name=product_name,
                new_price=new_price,
                old_price=old_price,
                url=product.get("url"),
                alerts_repo=alerts_repo,
            )
            result["notified"] = notified

        return result

    async def _send_notifications(
        self,
        platform: str,
        product_id: str,
        product_name: str,
        new_price: float,
        old_price: float,
        url: Optional[str],
        alerts_repo: AlertsRepository,
    ) -> bool:
        """
        Send notifications to users tracking this product.
        """
        alerts = alerts_repo.get_alerts_by_product(platform, product_id)

        if not alerts:
            return False

        any_sent = False

        for alert in alerts:
            chat_id = alert["chat_id"]
            target_price = alert.get("target_price")
            last_alert_price = alert.get("last_price")

            try:
                notification_sent = False

                # Check if target price reached
                if target_price and new_price <= target_price:
                    await self._send_target_reached_notification(
                        chat_id=chat_id,
                        product_name=product_name,
                        current_price=new_price,
                        target_price=target_price,
                        url=url,
                        platform=platform,
                    )
                    notification_sent = True

                # Check for price drop
                elif last_alert_price and new_price < last_alert_price:
                    await self._send_price_drop_notification(
                        chat_id=chat_id,
                        product_name=product_name,
                        old_price=last_alert_price,
                        new_price=new_price,
                        url=url,
                        platform=platform,
                    )
                    notification_sent = True

                # Update last price in alert
                alerts_repo.update_last_price(chat_id, platform, product_id, new_price)

                if notification_sent:
                    any_sent = True
                    logger.info(
                        f"Notification sent to {chat_id} for {platform}:{product_id}"
                    )

            except Exception as e:
                logger.error(f"Failed to send notification to {chat_id}: {e}")

        return any_sent

    async def _send_price_drop_notification(
        self,
        chat_id: int,
        product_name: str,
        old_price: float,
        new_price: float,
        url: Optional[str],
        platform: str,
    ) -> bool:
        """Send price drop notification via Telegram bot."""
        from backend.telegram_bot import get_bot

        bot = get_bot()
        if not bot:
            return False

        platform_emoji = "🟣" if platform == "wb" else "🔵"
        platform_name = "Wildberries" if platform == "wb" else "Ozon"

        diff = old_price - new_price
        diff_percent = (diff / old_price) * 100 if old_price > 0 else 0

        short_name = (
            product_name[:50] + "..." if len(product_name) > 50 else product_name
        )

        message = f"""📉 <b>Изменение цены!</b>

{platform_emoji} <b>{platform_name}</b>
📦 {short_name}

💰 Было: {old_price:,.0f} ₽
💰 Стало: <b>{new_price:,.0f} ₽</b>

Упала на {diff_percent:.1f}% ({diff:,.0f} ₽)
"""
        return await self._send_telegram_message(chat_id, message, url)

    async def _send_target_reached_notification(
        self,
        chat_id: int,
        product_name: str,
        current_price: float,
        target_price: float,
        url: Optional[str],
        platform: str,
    ) -> bool:
        """Send target price reached notification."""
        from backend.telegram_bot import get_bot

        bot = get_bot()
        if not bot:
            return False

        platform_emoji = "🟣" if platform == "wb" else "🔵"
        platform_name = "Wildberries" if platform == "wb" else "Ozon"

        short_name = (
            product_name[:50] + "..." if len(product_name) > 50 else product_name
        )

        message = f"""🎯 <b>Целевая цена достигнута!</b>

{platform_emoji} <b>{platform_name}</b>
📦 {short_name}

💰 Текущая цена: <b>{current_price:,.0f} ₽</b>
🎯 Ваша цель: {target_price:,.0f} ₽

Самое время покупать! 🛍️
"""
        return await self._send_telegram_message(chat_id, message, url)

    async def _send_telegram_message(
        self, chat_id: int, message: str, url: Optional[str]
    ) -> bool:
        """Send a message via Telegram bot."""
        from backend.telegram_bot import get_bot

        bot = get_bot()
        if not bot:
            return False

        try:
            from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

            keyboard = None
            if url:
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="🛒 Открыть товар", url=url)]
                    ]
                )

            await bot.send_message(
                chat_id,
                message,
                parse_mode="HTML",
                disable_web_page_preview=True,
                reply_markup=keyboard,
            )
            return True

        except Exception as e:
            logger.error(f"Failed to send Telegram message to {chat_id}: {e}")
            return False

    def run_once_sync(self) -> dict:
        """
        Synchronously run a single crawl (for manual triggers).

        Returns:
            Crawl statistics
        """
        return asyncio.run(self.crawl_once())


# Global crawler instance
crawler = CrawlerService()
