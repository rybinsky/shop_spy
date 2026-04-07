"""
ShopSpy - Prices Repository

Database operations for price tracking and history.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from backend.db.database import Database

logger = logging.getLogger(__name__)


class PricesRepository:
    """Repository for price-related database operations."""

    def __init__(self, db: Database):
        """
        Initialize repository.

        Args:
            db: Database instance
        """
        self.db = db

    def record_price(
        self,
        platform: str,
        product_id: str,
        price: float,
        product_name: Optional[str] = None,
        original_price: Optional[float] = None,
        url: Optional[str] = None,
    ) -> tuple[bool, Optional[float]]:
        """
        Record a price entry.

        Args:
            platform: Platform identifier ('wb' or 'ozon')
            product_id: Product ID on the platform
            price: Current price
            product_name: Product name (optional)
            original_price: Original price before discount (optional)
            url: Product URL (optional)

        Returns:
            Tuple of (was_saved, previous_price)
            - was_saved: True if price was saved (new or changed)
            - previous_price: Previous price if existed, None otherwise
        """
        with self.db.get_connection() as conn:
            # Get last price entry
            last = conn.execute(
                """SELECT price, recorded_at FROM prices
                   WHERE platform = ? AND product_id = ?
                   ORDER BY recorded_at DESC LIMIT 1""",
                (platform, product_id),
            ).fetchone()

            old_price = last["price"] if last else None

            # Skip if same price recorded recently (within 6 hours)
            if last and abs(last["price"] - price) < 0.01:
                last_dt = datetime.fromisoformat(last["recorded_at"])
                if datetime.now() - last_dt < timedelta(hours=6):
                    logger.debug(
                        f"Skipping duplicate price for {platform}:{product_id}"
                    )
                    return False, old_price

            # Insert new price record
            conn.execute(
                """INSERT INTO prices
                   (platform, product_id, product_name, price, original_price, url)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (platform, product_id, product_name, price, original_price, url),
            )

            logger.info(
                f"Recorded price for {platform}:{product_id}: {price} ₽"
                + (f" (was {old_price} ₽)" if old_price else "")
            )
            return True, old_price

    def get_price_history(
        self, platform: str, product_id: str, limit: int = 30
    ) -> list[dict]:
        """
        Get price history for a product.

        Args:
            platform: Platform identifier
            product_id: Product ID
            limit: Maximum number of records to return

        Returns:
            List of price history entries (oldest first)
        """
        with self.db.get_connection() as conn:
            rows = conn.execute(
                """SELECT price, original_price, recorded_at
                   FROM prices
                   WHERE platform = ? AND product_id = ?
                   ORDER BY recorded_at DESC LIMIT ?""",
                (platform, product_id, limit),
            ).fetchall()

            # Return in chronological order (oldest first)
            history = [
                {
                    "price": row["price"],
                    "original_price": row["original_price"],
                    "recorded_at": row["recorded_at"],
                }
                for row in reversed(rows)
            ]

            logger.debug(
                f"Retrieved {len(history)} price records for {platform}:{product_id}"
            )
            return history

    def get_last_price(self, platform: str, product_id: str) -> Optional[float]:
        """
        Get the most recent price for a product.

        Args:
            platform: Platform identifier
            product_id: Product ID

        Returns:
            Last recorded price or None
        """
        with self.db.get_connection() as conn:
            row = conn.execute(
                """SELECT price FROM prices
                   WHERE platform = ? AND product_id = ?
                   ORDER BY recorded_at DESC LIMIT 1""",
                (platform, product_id),
            ).fetchone()
            return row["price"] if row else None

    def get_tracked_products(self, limit: int = 100) -> list[dict]:
        """
        Get list of all tracked products with aggregated data.

        Args:
            limit: Maximum number of products to return

        Returns:
            List of products with min/max prices and record counts
        """
        with self.db.get_connection() as conn:
            rows = conn.execute(
                """SELECT platform, product_id, product_name, url,
                          MIN(price) as min_price,
                          MAX(price) as max_price,
                          COUNT(*) as records,
                          MAX(recorded_at) as last_seen
                   FROM prices
                   GROUP BY platform, product_id
                   ORDER BY last_seen DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()

            products = [dict(row) for row in rows]
            logger.debug(f"Retrieved {len(products)} tracked products")
            return products

    def get_products_for_crawl(self) -> list[dict]:
        """
        Get unique products for crawler to check.

        Returns:
            List of products with platform, product_id, name, and url
        """
        with self.db.get_connection() as conn:
            rows = conn.execute(
                """SELECT DISTINCT platform, product_id, product_name, url
                   FROM prices
                   ORDER BY recorded_at DESC"""
            ).fetchall()

            # Deduplicate
            seen = set()
            products = []
            for row in rows:
                key = f"{row['platform']}:{row['product_id']}"
                if key not in seen:
                    seen.add(key)
                    products.append(dict(row))

            logger.info(f"Found {len(products)} products to crawl")
            return products

    def get_stats(self) -> dict:
        """
        Get price tracking statistics.

        Returns:
            Dictionary with total_records, unique_products, and platform breakdown
        """
        with self.db.get_connection() as conn:
            total_records = conn.execute(
                "SELECT COUNT(*) as count FROM prices"
            ).fetchone()["count"]

            unique_products = conn.execute(
                "SELECT COUNT(DISTINCT platform || product_id) as count FROM prices"
            ).fetchone()["count"]

            platform_rows = conn.execute(
                """SELECT platform, COUNT(DISTINCT product_id) as count
                   FROM prices
                   GROUP BY platform"""
            ).fetchall()

            platforms = {row["platform"]: row["count"] for row in platform_rows}

            return {
                "total_records": total_records,
                "unique_products": unique_products,
                "platforms": platforms,
            }

    def cleanup_old_records(self, days: int = 365) -> int:
        """
        Remove price records older than specified days.

        Args:
            days: Number of days to keep

        Returns:
            Number of deleted records
        """
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                """DELETE FROM prices
                   WHERE recorded_at < datetime('now', ?)""",
                (f"-{days} days",),
            )
            deleted = cursor.rowcount

            if deleted > 0:
                logger.info(
                    f"Cleaned up {deleted} old price records (older than {days} days)"
                )

            return deleted

    def get_recent_prices(self, limit: int = 20) -> list[dict]:
        """
        Get recent price records (for admin panel).

        Args:
            limit: Maximum number of records to return

        Returns:
            List of recent price records
        """
        with self.db.get_connection() as conn:
            rows = conn.execute(
                """SELECT platform, product_id, product_name, price,
                          original_price, url, recorded_at
                   FROM prices
                   ORDER BY recorded_at DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]
