"""
ShopSpy - Crawler Service

Background service for periodically checking prices and sending notifications.
Uses API first, batches failures into parallel Playwright scraping.
"""

import asyncio
import logging
from typing import Optional

import httpx

from backend.config import config
from backend.db import AlertsRepository, PricesRepository, get_database
from backend.services.price_analyzer import PriceAnalyzer
from backend.utils.marketplace_api import MarketplaceAPI, get_scraper

BATCH_SIZE = 5  # Parallel Playwright pages per batch

logger = logging.getLogger(__name__)


class CrawlerService:
    """Service for crawling prices and sending notifications."""

    def __init__(self):
        self.marketplace_api = MarketplaceAPI(
            timeout=config.crawler.timeout,
            max_retries=config.crawler.max_retries,
        )
        self.price_analyzer = PriceAnalyzer()
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._crawl_loop())
        logger.info(f"Crawler started. Interval: {config.crawler.interval_seconds // 3600}h")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        try:
            await get_scraper().close()
        except Exception:
            pass
        logger.info("Crawler stopped")

    async def _crawl_loop(self) -> None:
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            return

        while self._running:
            try:
                await self.crawl_once()
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.error(f"Crawl iteration failed: {e}")

            if not self._running:
                break

            logger.info(f"Next crawl in {config.crawler.interval_seconds // 3600}h")
            sleep_remaining = config.crawler.interval_seconds
            while sleep_remaining > 0 and self._running:
                try:
                    await asyncio.sleep(min(60, sleep_remaining))
                except asyncio.CancelledError:
                    return
                sleep_remaining -= 60

    async def crawl_once(self) -> dict:
        db = get_database()
        prices_repo = PricesRepository(db)
        alerts_repo = AlertsRepository(db)

        products = prices_repo.get_products_for_crawl()
        if not products:
            return {"checked": 0, "updated": 0, "notifications": 0, "errors": 0}

        stats = {"checked": 0, "updated": 0, "notifications": 0, "errors": 0}

        # Split by platform
        by_platform: dict[str, list[dict]] = {}
        for p in products:
            by_platform.setdefault(p["platform"], []).append(p)

        logger.info(
            f"Crawling {len(products)} products: "
            + ", ".join(f"{k}={len(v)}" for k, v in by_platform.items())
        )

        async with httpx.AsyncClient(
            headers=self.marketplace_api.default_headers,
            follow_redirects=True,
            timeout=config.crawler.timeout,
        ) as client:
            for platform, platform_products in by_platform.items():
                if not self._running:
                    break
                s = await self._crawl_platform(
                    client, platform, platform_products, prices_repo, alerts_repo
                )
                for k in stats:
                    stats[k] += s[k]

        logger.info(
            f"Crawl done: checked={stats['checked']} updated={stats['updated']} "
            f"notified={stats['notifications']} errors={stats['errors']}"
        )
        return stats

    async def _crawl_platform(
        self,
        client: httpx.AsyncClient,
        platform: str,
        products: list[dict],
        prices_repo: PricesRepository,
        alerts_repo: AlertsRepository,
    ) -> dict:
        """Crawl one platform: try API, batch-scrape failures via Playwright."""
        stats = {"checked": 0, "updated": 0, "notifications": 0, "errors": 0}
        api_failed: list[dict] = []

        # Phase 1: try API for all products
        for product in products:
            if not self._running:
                break
            try:
                price_data = await self._try_api(client, platform, product["product_id"])
                if price_data == "blocked":
                    api_failed.append(product)
                    continue
                if not price_data or price_data.get("price", 0) <= 0:
                    stats["checked"] += 1
                    continue
                r = await self._process_price_data(product, price_data, prices_repo, alerts_repo)
                stats["checked"] += 1
                if r.get("updated"):
                    stats["updated"] += 1
                if r.get("notified"):
                    stats["notifications"] += 1
            except asyncio.CancelledError:
                raise
            except Exception as e:
                stats["errors"] += 1
                logger.error(f"API {platform}:{product['product_id']}: {e}")

        # Phase 2: batch Playwright for blocked products
        if api_failed and self._running:
            logger.info(f"Playwright batch: {len(api_failed)} {platform} products")
            for i in range(0, len(api_failed), BATCH_SIZE):
                if not self._running:
                    break
                batch = api_failed[i : i + BATCH_SIZE]
                batch_ids = [p["product_id"] for p in batch]
                try:
                    scraper = get_scraper()
                    if platform == "wb":
                        results_map = await scraper.fetch_wb_batch(batch_ids)
                    else:
                        results_map = await scraper.fetch_ozon_batch(batch_ids)
                    for product in batch:
                        pid = product["product_id"]
                        price_data = results_map.get(pid)
                        stats["checked"] += 1
                        if price_data and price_data.get("price", 0) > 0:
                            r = await self._process_price_data(
                                product, price_data, prices_repo, alerts_repo
                            )
                            if r.get("updated"):
                                stats["updated"] += 1
                            if r.get("notified"):
                                stats["notifications"] += 1
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    stats["errors"] += len(batch)
                    logger.error(f"Playwright batch {platform}: {e}")

        return stats

    async def _try_api(
        self, client: httpx.AsyncClient, platform: str, product_id: str
    ):
        """Try API only. Returns 'blocked' on 403/429, price dict, or None."""
        if platform == "wb":
            url = "https://card.wb.ru/cards/v2/detail"
            params = {"appType": "1", "curr": "rub", "dest": "-1257786", "nm": product_id}
            try:
                resp = await client.get(url, params=params, timeout=self.marketplace_api.timeout)
                if resp.status_code in (403, 429):
                    return "blocked"
                if resp.status_code != 200:
                    return None
                data = resp.json()
                prods = data.get("data", {}).get("products", [])
                if not prods:
                    return None
                p = prods[0]
                sale = p.get("salePriceU", 0)
                orig = p.get("priceU", 0)
                price = sale / 100 if sale else 0
                if price <= 0:
                    return None
                return {
                    "price": price,
                    "original_price": orig / 100 if orig and orig / 100 > price else None,
                    "name": p.get("name", ""),
                }
            except Exception:
                return None

        elif platform == "ozon":
            url = "https://www.ozon.ru/api/entrypoint-api.bx/page/json/v2"
            params = {"url": f"/product/{product_id}"}
            headers = {
                **self.marketplace_api.default_headers,
                "Accept": "application/json",
                "Referer": f"https://www.ozon.ru/product/{product_id}",
            }
            try:
                resp = await client.get(
                    url, params=params, headers=headers, timeout=self.marketplace_api.timeout
                )
                if resp.status_code in (403, 429):
                    return "blocked"
                if resp.status_code != 200:
                    return None
                data = resp.json()
                price = self.marketplace_api._find_price_in_dict(data)
                if price and price > 0:
                    return {"price": price, "original_price": None, "name": ""}
                return None
            except Exception:
                return None

        return None

    async def _process_price_data(
        self, product: dict, price_data: dict,
        prices_repo: PricesRepository, alerts_repo: AlertsRepository,
    ) -> dict:
        result = {"updated": False, "notified": False}
        platform = product["platform"]
        product_id = product["product_id"]
        new_price = price_data["price"]
        product_name = price_data.get("name") or product.get("product_name", "")

        old_price = prices_repo.get_last_price(platform, product_id)
        saved, _ = prices_repo.record_price(
            platform=platform, product_id=product_id, price=new_price,
            product_name=product_name,
            original_price=price_data.get("original_price"),
            url=product.get("url"),
        )
        result["updated"] = saved

        if saved and old_price and new_price != old_price:
            notified = await self._send_notifications(
                platform=platform, product_id=product_id,
                product_name=product_name, new_price=new_price,
                old_price=old_price, url=product.get("url"),
                alerts_repo=alerts_repo,
            )
            result["notified"] = notified
        return result

    async def _send_notifications(
        self, platform: str, product_id: str, product_name: str,
        new_price: float, old_price: float, url: Optional[str],
        alerts_repo: AlertsRepository,
    ) -> bool:
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
                if target_price and new_price <= target_price:
                    await self._send_target_reached_notification(
                        chat_id, product_name, new_price, target_price, url, platform
                    )
                    notification_sent = True
                elif last_alert_price and new_price < last_alert_price:
                    await self._send_price_drop_notification(
                        chat_id, product_name, last_alert_price, new_price, url, platform
                    )
                    notification_sent = True

                alerts_repo.update_last_price(chat_id, platform, product_id, new_price)
                if notification_sent:
                    any_sent = True
                    logger.info(f"Notified {chat_id} for {platform}:{product_id}")
            except Exception as e:
                logger.error(f"Notification to {chat_id} failed: {e}")
        return any_sent

    async def _send_price_drop_notification(
        self, chat_id, product_name, old_price, new_price, url, platform
    ) -> bool:
        from backend.telegram_bot import get_bot
        bot = get_bot()
        if not bot:
            return False
        emoji = "\U0001f7e3" if platform == "wb" else "\U0001f535"
        name = "Wildberries" if platform == "wb" else "Ozon"
        diff = old_price - new_price
        pct = (diff / old_price) * 100 if old_price > 0 else 0
        short = product_name[:50] + "..." if len(product_name) > 50 else product_name
        msg = (
            f"\U0001f4c9 <b>Изменение цены!</b>\n\n"
            f"{emoji} <b>{name}</b>\n\U0001f4e6 {short}\n\n"
            f"\U0001f4b0 Было: {old_price:,.0f} ₽\n"
            f"\U0001f4b0 Стало: <b>{new_price:,.0f} ₽</b>\n\n"
            f"Упала на {pct:.1f}% ({diff:,.0f} ₽)\n"
        )
        return await self._send_telegram_message(chat_id, msg, url)

    async def _send_target_reached_notification(
        self, chat_id, product_name, current_price, target_price, url, platform
    ) -> bool:
        from backend.telegram_bot import get_bot
        bot = get_bot()
        if not bot:
            return False
        emoji = "\U0001f7e3" if platform == "wb" else "\U0001f535"
        name = "Wildberries" if platform == "wb" else "Ozon"
        short = product_name[:50] + "..." if len(product_name) > 50 else product_name
        msg = (
            f"\U0001f3af <b>Целевая цена достигнута!</b>\n\n"
            f"{emoji} <b>{name}</b>\n\U0001f4e6 {short}\n\n"
            f"\U0001f4b0 Текущая цена: <b>{current_price:,.0f} ₽</b>\n"
            f"\U0001f3af Ваша цель: {target_price:,.0f} ₽\n\n"
            f"Самое время покупать! \U0001f6cd\ufe0f\n"
        )
        return await self._send_telegram_message(chat_id, msg, url)

    async def _send_telegram_message(self, chat_id, message, url) -> bool:
        from backend.telegram_bot import get_bot
        bot = get_bot()
        if not bot:
            return False
        try:
            from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
            keyboard = None
            if url:
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text="\U0001f6d2 Открыть товар", url=url)]]
                )
            await bot.send_message(
                chat_id, message, parse_mode="HTML",
                disable_web_page_preview=True, reply_markup=keyboard,
            )
            return True
        except Exception as e:
            logger.error(f"Telegram send to {chat_id} failed: {e}")
            return False

    def run_once_sync(self) -> dict:
        return asyncio.run(self.crawl_once())


crawler = CrawlerService()
