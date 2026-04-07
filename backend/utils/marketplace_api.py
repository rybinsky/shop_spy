"""
ShopSpy - Marketplace API Utilities

Fetches prices from Wildberries and Ozon.
Tries public JSON APIs first, falls back to Playwright browser scraping on failure.
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

# Comprehensive stealth patches to avoid bot detection
_STEALTH_JS = """
// Hide webdriver
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
delete navigator.__proto__.webdriver;

// Chrome runtime
window.chrome = {
    runtime: {
        onConnect: {addListener: function(){}},
        onMessage: {addListener: function(){}},
    },
    loadTimes: function(){return{}},
    csi: function(){return{}},
};

// Plugins
Object.defineProperty(navigator, 'plugins', {
    get: () => {
        const plugins = [
            {name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer'},
            {name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai'},
            {name: 'Native Client', filename: 'internal-nacl-plugin'},
        ];
        plugins.length = 3;
        return plugins;
    }
});

// Languages
Object.defineProperty(navigator, 'languages', {get: () => ['ru-RU', 'ru', 'en-US', 'en']});
Object.defineProperty(navigator, 'language', {get: () => 'ru-RU'});

// Permissions
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) =>
    parameters.name === 'notifications'
        ? Promise.resolve({state: Notification.permission})
        : originalQuery(parameters);

// WebGL vendor
const getParameter = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function(parameter) {
    if (parameter === 37445) return 'Intel Inc.';
    if (parameter === 37446) return 'Intel Iris OpenGL Engine';
    return getParameter.call(this, parameter);
};

// Hide automation
Object.defineProperty(navigator, 'maxTouchPoints', {get: () => 0});
Object.defineProperty(navigator, 'connection', {
    get: () => ({effectiveType: '4g', rtt: 50, downlink: 10, saveData: false})
});
"""


class PlaywrightScraper:
    """Two browsers: headless for WB, visible for Ozon (blocks headless)."""

    def __init__(self, concurrency: int = 5):
        self._playwright = None
        self._wb_browser = None
        self._ozon_browser = None
        self._wb_context = None
        self._ozon_context = None
        self._init_lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(concurrency)

    async def _ensure_playwright(self):
        if self._playwright:
            return
        from playwright.async_api import async_playwright
        self._playwright = await async_playwright().start()

    async def _ensure_wb_browser(self):
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
            logger.info("WB browser launched (headless)")

    async def _ensure_ozon_browser(self):
        if self._ozon_browser and self._ozon_browser.is_connected():
            return
        async with self._init_lock:
            if self._ozon_browser and self._ozon_browser.is_connected():
                return
            await self._ensure_playwright()

            # Ozon blocks headless browsers. Use virtual display on servers.
            self._xvfb = None
            try:
                from xvfbwrapper import Xvfb
                self._xvfb = Xvfb(width=1280, height=720)
                self._xvfb.start()
                logger.info("Xvfb virtual display started for Ozon")
            except (ImportError, FileNotFoundError, OSError):
                # No Xvfb available (macOS/local) — fine, real display exists
                pass

            self._ozon_browser = await self._playwright.chromium.launch(
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
            )
            logger.info("Ozon browser launched (visible / virtual display)")

    async def _get_wb_context(self):
        """WB context with resource blocking for speed."""
        await self._ensure_wb_browser()
        if self._wb_context:
            return self._wb_context
        async with self._init_lock:
            if self._wb_context:
                return self._wb_context
            self._wb_context = await self._wb_browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                locale="ru-RU",
                viewport={"width": 1280, "height": 720},
            )
            await self._wb_context.route("**/*", self._wb_route_handler)
            return self._wb_context

    async def _new_ozon_context(self):
        """Fresh Ozon context each time — no stale cookies from blocked sessions."""
        await self._ensure_ozon_browser()
        return await self._ozon_browser.new_context()

    @staticmethod
    async def _wb_route_handler(route):
        if route.request.resource_type in _BLOCK_RESOURCE_TYPES:
            await route.abort()
        elif _BLOCK_URL_RE.search(route.request.url):
            await route.abort()
        else:
            await route.continue_()

    async def close(self):
        if self._wb_context:
            try:
                await self._wb_context.close()
            except Exception:
                pass
        self._wb_context = None
        for br in (self._wb_browser, self._ozon_browser):
            if br:
                try:
                    await br.close()
                except Exception:
                    pass
        self._wb_browser = None
        self._ozon_browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        if getattr(self, "_xvfb", None):
            self._xvfb.stop()
            self._xvfb = None

    # ── helpers ──

    @staticmethod
    def _parse_price(text: str) -> Optional[float]:
        val = re.sub(r"[^\d]", "", text or "")
        return float(val) if val else None

    async def _find_price(self, page, selectors: list[str], timeout: int = 5000) -> Optional[float]:
        for sel in selectors:
            try:
                el = await page.wait_for_selector(sel, timeout=timeout)
                if el:
                    p = self._parse_price(await el.text_content())
                    if p and p > 0:
                        return p
            except Exception:
                continue
        return None

    async def _find_text(self, page, selectors: list[str], min_len: int = 3) -> str:
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

    async def _find_price_no_wait(self, page, selectors: list[str]) -> Optional[float]:
        for sel in selectors:
            try:
                el = await page.query_selector(sel)
                if el:
                    p = self._parse_price(await el.text_content())
                    if p and p > 0:
                        return p
            except Exception:
                continue
        return None

    # ── WB ──

    async def fetch_wb_price(self, product_id: str) -> Optional[dict]:
        ctx = await self._get_wb_context()
        async with self._semaphore:
            page = await ctx.new_page()
            try:
                await page.goto(
                    f"https://www.wildberries.ru/catalog/{product_id}/detail.aspx",
                    wait_until="domcontentloaded",
                    timeout=15000,
                )
                price = await self._find_price(page, [
                    "ins.price-block__final-price",
                    ".price-block__final-price",
                    "ins.priceBlockFinalPrice--iToZR",
                    ".priceBlockFinalPrice--iToZR",
                ])
                if not price:
                    logger.warning(f"Playwright: no price for WB {product_id}")
                    return None

                original_price = await self._find_price_no_wait(page, [
                    "del.price-block__old-price",
                    ".price-block__old-price del",
                    "span.priceBlockOldPrice--qSWAf",
                    ".priceBlockOldPrice--qSWAf",
                ])
                if original_price and original_price <= price:
                    original_price = None

                name = await self._find_text(page, [
                    "h1.product-page__title",
                    "h2.productTitle--lfc4o",
                    ".productTitle--lfc4o",
                    "h1",
                ])

                logger.info(f"Playwright WB {product_id}: {price} / {original_price}")
                return {"price": price, "original_price": original_price, "name": name}
            except Exception as e:
                logger.error(f"Playwright WB {product_id}: {e}")
                return None
            finally:
                await page.close()

    # ── Ozon ──

    async def fetch_ozon_price(self, product_id: str) -> Optional[dict]:
        ctx = await self._new_ozon_context()
        async with self._semaphore:
            page = await ctx.new_page()
            try:
                await page.goto(
                    f"https://www.ozon.ru/product/{product_id}/",
                    timeout=60000,
                )

                # Wait for JS to render (matches working script)
                await page.wait_for_timeout(5000)

                # Wait for price widget
                try:
                    await page.wait_for_selector(
                        '[data-widget="webPrice"]', timeout=15000
                    )
                except Exception:
                    logger.warning(
                        f"Playwright: webPrice widget not found for Ozon {product_id}"
                    )
                    return None

                # Extract text from price widget and parse all prices
                widget = await page.query_selector('[data-widget="webPrice"]')
                widget_text = await widget.inner_text() if widget else ""

                numbers = []
                for raw in re.findall(r"(\d[\d\s\u00a0\u2009]*)\s*₽", widget_text):
                    clean = re.sub(r"[\s\u00a0\u2009]", "", raw)
                    if clean.isdigit() and int(clean) > 0:
                        numbers.append(float(clean))

                if not numbers:
                    logger.warning(
                        f"Playwright: no price in widget for Ozon {product_id}"
                    )
                    return None

                price = min(numbers)
                original_price = (
                    max(numbers) if len(numbers) > 1 and max(numbers) > price else None
                )

                name = await self._find_text(page, [
                    '[data-widget="webProductHeading"] h1',
                    "h1.tsHeadline550Medium",
                    "h1",
                ])

                logger.info(f"Playwright Ozon {product_id}: {price} / {original_price}")
                return {"price": price, "original_price": original_price, "name": name}
            except Exception as e:
                logger.error(f"Playwright Ozon {product_id}: {e}")
                return None
            finally:
                await ctx.close()

    # ── batch ──

    async def fetch_prices_batch(
        self, platform: str, product_ids: list[str]
    ) -> dict[str, Optional[dict]]:
        """Fetch multiple products in parallel (up to concurrency limit)."""
        fetch_fn = self.fetch_wb_price if platform == "wb" else self.fetch_ozon_price
        tasks = {pid: asyncio.create_task(fetch_fn(pid)) for pid in product_ids}
        results = {}
        for pid, task in tasks.items():
            try:
                results[pid] = await task
            except Exception as e:
                logger.error(f"Batch {platform} {pid}: {e}")
                results[pid] = None
        return results


# ── global instance ──

_scraper: Optional[PlaywrightScraper] = None


def get_scraper() -> PlaywrightScraper:
    global _scraper
    if _scraper is None:
        _scraper = PlaywrightScraper()
    return _scraper


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

    async def fetch_wb_price(
        self, client: httpx.AsyncClient, product_id: str
    ) -> Optional[dict]:
        url = "https://card.wb.ru/cards/v2/detail"
        params = {"appType": "1", "curr": "rub", "dest": "-1257786", "nm": product_id}

        try:
            response = await client.get(url, params=params, timeout=self.timeout)

            if response.status_code == 403:
                logger.warning(f"WB API 403 for {product_id}, using Playwright")
                return await get_scraper().fetch_wb_price(product_id)

            if response.status_code != 200:
                logger.warning(f"WB API {response.status_code} for {product_id}")
                return None

            data = response.json()
            products = data.get("data", {}).get("products", [])
            if not products:
                return None

            p = products[0]
            sale = p.get("salePriceU", 0)
            orig = p.get("priceU", 0)
            price = sale / 100 if sale else 0
            original_price = orig / 100 if orig and orig / 100 > price else None
            if price <= 0:
                return None

            return {"price": price, "original_price": original_price, "name": p.get("name", "")}

        except httpx.TimeoutException:
            logger.warning(f"WB API timeout for {product_id}")
            return None
        except Exception as e:
            logger.error(f"WB API error for {product_id}: {e}")
            return None

    async def fetch_ozon_price(
        self, client: httpx.AsyncClient, product_id: str
    ) -> Optional[dict]:
        url = "https://www.ozon.ru/api/entrypoint-api.bx/page/json/v2"
        params = {"url": f"/product/{product_id}"}
        headers = {
            **self.default_headers,
            "Accept": "application/json",
            "Referer": f"https://www.ozon.ru/product/{product_id}",
        }

        try:
            response = await client.get(url, params=params, headers=headers, timeout=self.timeout)

            if response.status_code in (403, 429):
                logger.warning(f"Ozon API {response.status_code} for {product_id}, using Playwright")
                return await get_scraper().fetch_ozon_price(product_id)

            if response.status_code != 200:
                logger.warning(f"Ozon API {response.status_code} for {product_id}")
                return None

            data = response.json()
            price = self._find_price_in_dict(data)
            if price and price > 0:
                return {"price": price, "original_price": None, "name": ""}
            return None

        except httpx.TimeoutException:
            logger.warning(f"Ozon API timeout for {product_id}")
            return None
        except Exception as e:
            logger.error(f"Ozon API error for {product_id}: {e}")
            return None

    def _find_price_in_dict(self, data, depth: int = 0) -> Optional[float]:
        if depth > 10:
            return None
        if isinstance(data, dict):
            for key in ("price", "finalPrice", "cardPrice", "salePrice"):
                if key in data:
                    value = data[key]
                    if isinstance(value, (int, float)) and value > 0:
                        return float(value)
                    if isinstance(value, str):
                        parsed = self._parse_price_string(value)
                        if parsed:
                            return parsed
            for value in data.values():
                result = self._find_price_in_dict(value, depth + 1)
                if result:
                    return result
        elif isinstance(data, list):
            for item in data[:20]:
                result = self._find_price_in_dict(item, depth + 1)
                if result:
                    return result
        return None

    @staticmethod
    def _parse_price_string(value: str) -> Optional[float]:
        try:
            clean = (
                value.replace("\u2009", "").replace("\u00a0", "")
                .replace(" ", "").replace(",", ".")
                .replace("₽", "").replace("руб.", "").strip()
            )
            return float(clean) if clean else None
        except (ValueError, AttributeError):
            return None

    async def fetch_price(
        self, client: httpx.AsyncClient, platform: str, product_id: str
    ) -> Optional[dict]:
        if platform == "wb":
            return await self.fetch_wb_price(client, product_id)
        elif platform == "ozon":
            return await self.fetch_ozon_price(client, product_id)
        else:
            logger.warning(f"Unknown platform: {platform}")
            return None


marketplace_api = MarketplaceAPI()
