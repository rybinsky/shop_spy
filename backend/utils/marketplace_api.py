"""
ShopSpy - Marketplace API Utilities

Functions for fetching prices from Wildberries and Ozon public APIs.
"""

import asyncio
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class MarketplaceAPI:
    """Handles API calls to different marketplaces."""

    def __init__(self, timeout: int = 10, max_retries: int = 3):
        """
        Initialize API client.

        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries for failed requests
        """
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
        """
        Fetch price from Wildberries API.

        Args:
            client: httpx AsyncClient instance
            product_id: Wildberries product ID (nmId)

        Returns:
            Dictionary with price data or None if failed:
            {
                "price": float,
                "original_price": float | None,
                "name": str
            }
        """
        url = f"https://card.wb.ru/cards/v2/detail"
        params = {
            "appType": "1",
            "curr": "rub",
            "dest": "-1257786",
            "nm": product_id,
        }

        try:
            response = await client.get(url, params=params, timeout=self.timeout)

            if response.status_code != 200:
                logger.warning(
                    f"WB API returned {response.status_code} for product {product_id}"
                )
                return None

            data = response.json()
            products = data.get("data", {}).get("products", [])

            if not products:
                logger.debug(f"WB product {product_id} not found in response")
                return None

            product = products[0]
            sale_price_u = product.get("salePriceU", 0)
            price_u = product.get("priceU", 0)
            name = product.get("name", "")

            # Convert from kopecks to rubles
            price = sale_price_u / 100 if sale_price_u else 0
            original_price = price_u / 100 if price_u and price_u > price else None

            if price <= 0:
                logger.debug(f"WB product {product_id} has invalid price: {price}")
                return None

            logger.debug(
                f"WB {product_id}: price={price}, original={original_price}, name={name[:30]}..."
            )

            return {
                "price": price,
                "original_price": original_price,
                "name": name,
            }

        except httpx.TimeoutException:
            logger.warning(f"WB API timeout for product {product_id}")
            return None
        except httpx.HTTPStatusError as e:
            logger.warning(f"WB API HTTP error for {product_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"WB API unexpected error for {product_id}: {e}")
            return None

    async def fetch_ozon_price(
        self, client: httpx.AsyncClient, product_id: str
    ) -> Optional[dict]:
        """
        Fetch price from Ozon API.
        Note: Ozon API is less reliable than WB and may require updates.

        Args:
            client: httpx AsyncClient instance
            product_id: Ozon product ID (SKU)

        Returns:
            Dictionary with price data or None if failed
        """
        url = f"https://www.ozon.ru/api/entrypoint-api.bx/page/json/v2"
        params = {"url": f"/product/{product_id}"}

        headers = {
            **self.default_headers,
            "Accept": "application/json",
            "Referer": f"https://www.ozon.ru/product/{product_id}",
        }

        try:
            response = await client.get(
                url, params=params, headers=headers, timeout=self.timeout
            )

            if response.status_code != 200:
                logger.warning(
                    f"Ozon API returned {response.status_code} for product {product_id}"
                )
                return None

            data = response.json()
            price = self._find_price_in_dict(data)

            if price and price > 0:
                logger.debug(f"Ozon {product_id}: price={price}")
                return {
                    "price": price,
                    "original_price": None,
                    "name": "",
                }

            return None

        except httpx.TimeoutException:
            logger.warning(f"Ozon API timeout for product {product_id}")
            return None
        except httpx.HTTPStatusError as e:
            logger.warning(f"Ozon API HTTP error for {product_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Ozon API unexpected error for {product_id}: {e}")
            return None

    def _find_price_in_dict(self, data: any, depth: int = 0) -> Optional[float]:
        """
        Recursively search for price in Ozon API response.

        Args:
            data: JSON data to search
            depth: Current recursion depth

        Returns:
            Price value or None
        """
        if depth > 10:  # Prevent infinite recursion
            return None

        if isinstance(data, dict):
            # Look for common price field names
            for key in ("price", "finalPrice", "cardPrice", "salePrice"):
                if key in data:
                    value = data[key]
                    if isinstance(value, (int, float)) and value > 0:
                        return float(value)
                    if isinstance(value, str):
                        parsed = self._parse_price_string(value)
                        if parsed:
                            return parsed

            # Recurse into values
            for value in data.values():
                result = self._find_price_in_dict(value, depth + 1)
                if result:
                    return result

        elif isinstance(data, list):
            for item in data[:20]:  # Limit items to check
                result = self._find_price_in_dict(item, depth + 1)
                if result:
                    return result

        return None

    def _parse_price_string(self, value: str) -> Optional[float]:
        """
        Parse price from string, handling various formats.

        Args:
            value: Price string (e.g., "1 299 ₽", "1299.00")

        Returns:
            Parsed price or None
        """
        try:
            # Remove common formatting
            clean = (
                value.replace("\u2009", "")  # Thin space
                .replace("\u00a0", "")  # Non-breaking space
                .replace(" ", "")
                .replace(",", ".")
                .replace("₽", "")
                .replace("руб.", "")
                .strip()
            )
            if clean:
                return float(clean)
        except (ValueError, AttributeError):
            pass
        return None

    async def fetch_price(
        self, client: httpx.AsyncClient, platform: str, product_id: str
    ) -> Optional[dict]:
        """
        Fetch price from the appropriate marketplace.

        Args:
            client: httpx AsyncClient instance
            platform: Platform identifier ('wb' or 'ozon')
            product_id: Product ID

        Returns:
            Dictionary with price data or None if failed
        """
        if platform == "wb":
            return await self.fetch_wb_price(client, product_id)
        elif platform == "ozon":
            return await self.fetch_ozon_price(client, product_id)
        else:
            logger.warning(f"Unknown platform: {platform}")
            return None


# Global instance
marketplace_api = MarketplaceAPI()
