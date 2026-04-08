"""
ShopSpy - User Statistics Repository

Database operations for user statistics, views tracking, and savings calculations.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from backend.db.database import Database

logger = logging.getLogger(__name__)


class UserStatsRepository:
    """Repository for user statistics operations."""

    def __init__(self, db: Database):
        """
        Initialize repository.

        Args:
            db: Database instance
        """
        self.db = db

    def record_view(
        self,
        telegram_id: int,
        platform: str,
        product_id: str,
        product_name: Optional[str] = None,
        price: Optional[float] = None,
        card_price: Optional[float] = None,
        avg_price: Optional[float] = None,
        original_price: Optional[float] = None,
    ) -> None:
        """
        Record a product view by user.

        Args:
            telegram_id: Telegram user ID
            platform: Platform identifier ('wb' or 'ozon')
            product_id: Product ID on the platform
            product_name: Product name (optional)
            price: Current price (optional)
            card_price: Card/wallet price (optional)
            avg_price: Average price from history (optional)
            original_price: Original/struck-through price (optional)
        """
        # Calculate saved amount
        saved_amount = 0.0
        if avg_price and price and price < avg_price:
            saved_amount = avg_price - price

        with self.db.get_connection() as conn:
            # Check if user already viewed this product recently (within 24 hours)
            recent = conn.execute(
                """SELECT id FROM user_stats
                   WHERE telegram_id = ? AND platform = ? AND product_id = ?
                   AND created_at > datetime('now', '-1 day')""",
                (telegram_id, platform, product_id),
            ).fetchone()

            if recent:
                logger.debug(
                    f"Skipping duplicate view for {telegram_id}:{platform}:{product_id}"
                )
                return

            conn.execute(
                """INSERT INTO user_stats
                   (telegram_id, platform, product_id, product_name, price,
                    card_price, avg_price, original_price, saved_amount, action)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'view')""",
                (
                    telegram_id,
                    platform,
                    product_id,
                    product_name,
                    price,
                    card_price,
                    avg_price,
                    original_price,
                    saved_amount,
                ),
            )

            logger.debug(
                f"Recorded view for user {telegram_id}: {platform}:{product_id}"
            )

    def get_user_summary(self, telegram_id: int) -> dict:
        """
        Get user statistics summary.

        Args:
            telegram_id: Telegram user ID

        Returns:
            Dictionary with summary statistics
        """
        with self.db.get_connection() as conn:
            # Total views
            total_viewed = conn.execute(
                "SELECT COUNT(DISTINCT platform || product_id) as count FROM user_stats WHERE telegram_id = ?",
                (telegram_id,),
            ).fetchone()["count"]

            # Total saved
            total_saved = conn.execute(
                "SELECT COALESCE(SUM(saved_amount), 0) as total FROM user_stats WHERE telegram_id = ?",
                (telegram_id,),
            ).fetchone()["total"]

            # Best deal
            best_deal = conn.execute(
                """SELECT product_name, platform, product_id, price, card_price,
                          original_price, saved_amount
                   FROM user_stats
                   WHERE telegram_id = ? AND saved_amount > 0
                   ORDER BY saved_amount DESC LIMIT 1""",
                (telegram_id,),
            ).fetchone()

            # Views this month
            month_start = datetime.now().replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
            monthly_views = conn.execute(
                """SELECT COUNT(*) as count FROM user_stats
                   WHERE telegram_id = ? AND created_at >= ?""",
                (telegram_id, month_start.isoformat()),
            ).fetchone()["count"]

            # Monthly saved
            monthly_saved = conn.execute(
                """SELECT COALESCE(SUM(saved_amount), 0) as total FROM user_stats
                   WHERE telegram_id = ? AND created_at >= ?""",
                (telegram_id, month_start.isoformat()),
            ).fetchone()["total"]

            return {
                "total_viewed": total_viewed,
                "total_saved": round(total_saved, 2),
                "monthly_views": monthly_views,
                "monthly_saved": round(monthly_saved, 2),
                "best_deal": dict(best_deal) if best_deal else None,
            }

    def get_user_products(self, telegram_id: int, limit: int = 50) -> list[dict]:
        """
        Get list of products viewed by user.

        Args:
            telegram_id: Telegram user ID
            limit: Maximum number of products to return

        Returns:
            List of product dictionaries
        """
        with self.db.get_connection() as conn:
            rows = conn.execute(
                """SELECT DISTINCT platform, product_id, product_name, price,
                          card_price, original_price, saved_amount,
                          MAX(created_at) as last_view
                   FROM user_stats
                   WHERE telegram_id = ?
                   GROUP BY platform, product_id
                   ORDER BY last_view DESC
                   LIMIT ?""",
                (telegram_id, limit),
            ).fetchall()

            return [dict(row) for row in rows]

    def get_activity_stats(self, telegram_id: int, days: int = 30) -> list[dict]:
        """
        Get user activity stats for the last N days.

        Args:
            telegram_id: Telegram user ID
            days: Number of days to look back

        Returns:
            List of daily activity dictionaries
        """
        with self.db.get_connection() as conn:
            rows = conn.execute(
                """SELECT date(created_at) as date,
                          COUNT(*) as views,
                          SUM(saved_amount) as saved
                   FROM user_stats
                   WHERE telegram_id = ?
                   AND created_at >= datetime('now', ?)
                   GROUP BY date(created_at)
                   ORDER BY date DESC""",
                (telegram_id, f"-{days} days"),
            ).fetchall()

            return [dict(row) for row in rows]

    def get_stats_leaderboard(self, limit: int = 10) -> list[dict]:
        """
        Get leaderboard of top savers.

        Args:
            limit: Maximum number of users to return

        Returns:
            List of user statistics dictionaries
        """
        with self.db.get_connection() as conn:
            rows = conn.execute(
                """SELECT telegram_id,
                          COUNT(DISTINCT platform || product_id) as total_viewed,
                          SUM(saved_amount) as total_saved
                   FROM user_stats
                   GROUP BY telegram_id
                   ORDER BY total_saved DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()

            return [dict(row) for row in rows]

    def cleanup_old_stats(self, days: int = 365) -> int:
        """
        Remove statistics older than specified days.

        Args:
            days: Number of days to keep

        Returns:
            Number of deleted records
        """
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM user_stats WHERE created_at < datetime('now', ?)",
                (f"-{days} days",),
            )
            deleted = cursor.rowcount

            if deleted > 0:
                logger.info(f"Cleaned up {deleted} old user stats records")

            return deleted
