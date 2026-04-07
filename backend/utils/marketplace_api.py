"""
ShopSpy - Marketplace API Utilities

Fetches prices from Wildberries and Ozon.
- WB: JSON API → Playwright headless fallback
- Ozon: JSON API → Playwright visible fallback (Ozon blocks all headless)
"""

import asyncio
import logging
import re
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_BLOCK_RESOURCE_TYPES = {"image", "media", "font"}
_BLOCK_URL_RE = re.compile(
    r"(analytics|tracking|metric|google|facebook|yandex.*metrika|ad\.|tns-counter|top-fwz|mail\.ru/counter)"
)


class PlaywrightScraper:
    """
    WB: headless Playwright (fast, WB doesn't block).
    Ozon: visible Playwright (Ozon blocks ALL headless).
          On servers uses Xvfb virtual display via Docker.
    """

    def __init__(self, concurrency: int = 5):
        self._playwright = None
        self._wb_browser = None
        self._ozon_browser = None
        self._wb_context = None
        self._init_lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(concurrency)

    async def _ensure_playwright(self):
        if self._playwright:
            return
        from playwright.async_api import async_playwright
        self._playwright = await async_playwright().start()

    # ── WB browser (headless) ──

    async def _ensure_wb(self):
        if self._wb_browser and self._wb_browser.is_connected():
            return
        async with self._init_lock:
            if self._wb_browser and self._wb_browser.is_connected():
                return
            await self._ensure_playwright()
            self._wb_browser = await self._playwright.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-gpu",
                    "--disable-dev-shm-usage",
                ],
            )
            self._wb_context = await self._wb_browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                locale="ru-RU",
                viewport={"width": 1280, "height": 720},
            )
            await self._wb_context.route("**/*", self._wb_route)
            logger.info("WB browser launched (headless)")

    @staticmethod
    async def _wb_route(route):
        if route.request.resource_type in _BLOCK_RESOURCE_TYPES:
            await route.abort()
        elif _BLOCK_URL_RE.search(route.request.url):
            await route.abort()
        else:
            await route.continue_()

    # ── Ozon browser (visible) ──

    async def _ensure_ozon(self):
        if self._ozon_browser and self._ozon_browser.is_connected():
            return
        async with self._init_lock:
            if self._ozon_browser and self._ozon_browser.is_connected():
                return
            await self._ensure_playwright()
            self._ozon_browser = await self._playwright.chromium.launch(
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
            )
            logger.info("Ozon browser launched (visible)")

    # ── cleanup ──

    async def close(self):
        for ctx in [self._wb_context]:
            if ctx:
                try:
                    await ctx.close()
                except Exception:
                    pass
        for br in [self._wb_browser, self._ozon_browser]:
            if br:
                try:
                    await br.close()
                except Exception:
                    pass
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
        self._wb_context = None
        self._wb_browser = None
        self._ozon_browser = None
        self._playwright = None

    # ── WB fetch ──

    async def fetch_wb_price(self, product_id: str) -> Optional[dict]:
        await self._ensure_wb()
        async with self._semaphore:
            page = await self._wb_context.new_page()
            try:
                await page.goto(
                    f"https://www.wildberries.ru/catalog/{product_id}/detail.aspx",
                    wait_until="domcontentloaded",
                    timeout=15000,
                )
                price = await self._extract_price(page, [
                    "ins.price-block__final-price",
                    ".price-block__final-price",
                    "ins.priceBlockFinalPrice--iToZR",
                    ".priceBlockFinalPrice--iToZR",
                ])
                if not price:
                    logger.warning(f"Playwright: no price for WB {product_id}")
                    return None

                original_price = await self._query_price(page, [
                    "del.price-block__old-price",
                    ".price-block__old-price del",
                    "span.priceBlockOldPrice--qSWAf",
                    ".priceBlockOldPrice--qSWAf",
                ])
                if original_price and original_price <= price:
                    original_price = None

                name = await self._query_text(page, [
                    "h1.product-page__title", "h2.productTitle--lfc4o",
                    ".productTitle--lfc4o", "h1",
                ])

                logger.info(f"WB {product_id}: {price} / {original_price}")
                return {"price": price, "original_price": original_price, "name": name}
            except Exception as e:
                logger.error(f"WB {product_id}: {e}")
                return None
            finally:
                await page.close()

    # ── Ozon fetch ──

    async def fetch_ozon_price(self, product_id: str) -> Optional[dict]:
        await self._ensure_ozon()
        # Fresh context each time — no stale cookies from blocks
        ctx = await self._ozon_browser.new_context()
        async with self._semaphore:
            page = await ctx.new_page()
            try:
                await page.goto(
                    f"https://www.ozon.ru/product/{product_id}/",
                    timeout=60000,
                )
                await page.wait_for_timeout(5000)

                try:
                    await page.wait_for_selector(
                        '[data-widget="webPrice"]', timeout=15000
                    )
                except Exception:
                    logger.warning(f"Ozon {product_id}: webPrice not found")
                    return None

                widget = await page.query_selector('[data-widget="webPrice"]')
                widget_text = await widget.inner_text() if widget else ""

                numbers = []
                for raw in re.findall(r"(\d[\d\s\u00a0\u2009]*)\s*₽", widget_text):
                    clean = re.sub(r"[\s\u00a0\u2009]", "", raw)
                    if clean.isdigit() and int(clean) > 0:
                        numbers.append(float(clean))

                if not numbers:
                    logger.warning(f"Ozon {product_id}: no prices in widget")
                    return None

                price = min(numbers)
                original_price = (
                    max(numbers) if len(numbers) > 1 and max(numbers) > price else None
                )

                name = await self._query_text(page, [
                    '[data-widget="webProductHeading"] h1',
                    "h1.tsHeadline550Medium", "h1",
                ])

                logger.info(f"Ozon {product_id}: {price} / {original_price}")
                return {"price": price, "original_price": original_price, "name": name}
            except Exception as e:
                logger.error(f"Ozon {product_id}: {e}")
                return None
            finally:
                await ctx.close()

    # ── batch ──

    async def fetch_wb_batch(self, ids: list[str]) -> dict[str, Optional[dict]]:
        tasks = {pid: asyncio.create_task(self.fetch_wb_price(pid)) for pid in ids}
        return {pid: await t for pid, t in tasks.items()}

    async def fetch_ozon_batch(self, ids: list[str]) -> dict[str, Optional[dict]]:
        tasks = {pid: asyncio.create_task(self.fetch_ozon_price(pid)) for pid in ids}
        return {pid: await t for pid, t in tasks.items()}

    # ── helpers ──

    async def _extract_price(self, page, selectors, timeout=5000) -> Optional[float]:
        for sel in selectors:
            try:
                el = await page.wait_for_selector(sel, timeout=timeout)
                if el:
                    val = re.sub(r"[^\d]", "", await el.text_content() or "")
                    if val:
                        return float(val)
            except Exception:
                continue
        return None

    async def _query_price(self, page, selectors) -> Optional[float]:
        for sel in selectors:
            try:
                el = await page.query_selector(sel)
                if el:
                    val = re.sub(r"[^\d]", "", await el.text_content() or "")
                    if val and float(val) > 0:
                        return float(val)
            except Exception:
                continue
        return None

    async def _query_text(self, page, selectors, min_len=3) -> str:
        for sel in selectors:
            try:
                el = await page.query_selector(sel)
                if el:
                    t = (await el.text_content() or "").strip()
                    if len(t) > min_len:
                        return t
            except Exception:
                continue
        return ""


# ── Global instance ──

_scraper: Optional[PlaywrightScraper] = None


def get_scraper() -> PlaywrightScraper:
    global _scraper
    if _scraper is None:
        _scraper = PlaywrightScraper()
    return _scraper


# ── MarketplaceAPI ──


class MarketplaceAPI:
    """Tries JSON APIs first, falls back to Playwright."""

    def __init__(self, timeout: int = 10, max_retries: int = 3):
        self.timeout = timeout
        self.max_retries = max_retries
        self.default_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        }

    async def fetch_wb_price(self, client: httpx.AsyncClient, product_id: str) -> Optional[dict]:
        url = "https://card.wb.ru/cards/v2/detail"
        params = {"appType": "1", "curr": "rub", "dest": "-1257786", "nm": product_id}
        try:
            resp = await client.get(url, params=params, timeout=self.timeout)
            if resp.status_code == 403:
                logger.warning(f"WB API 403 for {product_id}, using Playwright")
                return await get_scraper().fetch_wb_price(product_id)
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
            original_price = orig / 100 if orig and orig / 100 > price else None
            if price <= 0:
                return None
            return {"price": price, "original_price": original_price, "name": p.get("name", "")}
        except httpx.TimeoutException:
            return None
        except Exception as e:
            logger.error(f"WB API {product_id}: {e}")
            return None

    async def fetch_ozon_price(self, client: httpx.AsyncClient, product_id: str) -> Optional[dict]:
        url = "https://www.ozon.ru/api/entrypoint-api.bx/page/json/v2"
        params = {"url": f"/product/{product_id}"}
        headers = {**self.default_headers, "Accept": "application/json",
                   "Referer": f"https://www.ozon.ru/product/{product_id}"}
        try:
            resp = await client.get(url, params=params, headers=headers, timeout=self.timeout)
            if resp.status_code in (403, 429):
                logger.warning(f"Ozon API {resp.status_code} for {product_id}, using Playwright")
                return await get_scraper().fetch_ozon_price(product_id)
            if resp.status_code != 200:
                return None
            data = resp.json()
            price = self._find_price_in_dict(data)
            if price and price > 0:
                return {"price": price, "original_price": None, "name": ""}
            return None
        except httpx.TimeoutException:
            return None
        except Exception as e:
            logger.error(f"Ozon API {product_id}: {e}")
            return None

    def _find_price_in_dict(self, data, depth=0) -> Optional[float]:
        if depth > 10:
            return None
        if isinstance(data, dict):
            for key in ("price", "finalPrice", "cardPrice", "salePrice"):
                if key in data:
                    v = data[key]
                    if isinstance(v, (int, float)) and v > 0:
                        return float(v)
                    if isinstance(v, str):
                        p = self._parse_price_string(v)
                        if p:
                            return p
            for v in data.values():
                r = self._find_price_in_dict(v, depth + 1)
                if r:
                    return r
        elif isinstance(data, list):
            for item in data[:20]:
                r = self._find_price_in_dict(item, depth + 1)
                if r:
                    return r
        return None

    @staticmethod
    def _parse_price_string(value: str) -> Optional[float]:
        try:
            clean = (value.replace("\u2009", "").replace("\u00a0", "")
                     .replace(" ", "").replace(",", ".")
                     .replace("₽", "").replace("руб.", "").strip())
            return float(clean) if clean else None
        except (ValueError, AttributeError):
            return None

    async def fetch_price(self, client: httpx.AsyncClient, platform: str, product_id: str) -> Optional[dict]:
        if platform == "wb":
            return await self.fetch_wb_price(client, product_id)
        elif platform == "ozon":
            return await self.fetch_ozon_price(client, product_id)
        return None


marketplace_api = MarketplaceAPI()
