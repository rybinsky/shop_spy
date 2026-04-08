"""
ShopSpy - User Statistics Repository

Database operations for user statistics, views tracking, savings calculations,
and user purchases.
"""

import logging
from datetime import datetime
from typing import Optional

from backend.db.database import Database

logger = logging.getLogger(__name__)


class UserStatsRepository:
    """Repository for user statistics operations."""

    VIEW_ACTION = "view"
    PURCHASE_DATE_ERROR = "purchase_date must be ISO date or datetime"

    def __init__(self, db: Database):
        """
        Initialize repository.

        Args:
            db: Database instance
        """
        self.db = db

    @staticmethod
    def _round_money(value: Optional[float]) -> float:
        """Round monetary value to 2 digits."""
        return round(float(value or 0), 2)

    @classmethod
    def _calculate_saved_amount(
        cls,
        baseline_price: Optional[float],
        actual_price: Optional[float],
    ) -> float:
        """Calculate savings against a baseline price."""
        if baseline_price is None or actual_price is None:
            return 0.0
        if actual_price >= baseline_price:
            return 0.0
        return cls._round_money(baseline_price - actual_price)

    @classmethod
    def _normalize_purchase_datetime(cls, purchase_date: Optional[str]) -> str:
        """Normalize purchase date to ISO datetime string."""
        if not purchase_date:
            return datetime.now().replace(microsecond=0).isoformat()

        normalized = purchase_date.strip().replace(" ", "T")
        if len(normalized) == 10:
            normalized = f"{normalized}T00:00:00"

        try:
            datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise ValueError(cls.PURCHASE_DATE_ERROR) from exc

        return normalized

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
        saved_amount = self._calculate_saved_amount(avg_price, price)

        with self.db.get_connection() as conn:
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
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                    self.VIEW_ACTION,
                ),
            )

            logger.debug(
                f"Recorded view for user {telegram_id}: {platform}:{product_id}"
            )

    def record_purchase(
        self,
        telegram_id: int,
        platform: str,
        product_id: str,
        purchase_price: float,
        product_name: Optional[str] = None,
        purchase_date: Optional[str] = None,
        current_price: Optional[float] = None,
        card_price: Optional[float] = None,
        avg_price: Optional[float] = None,
        original_price: Optional[float] = None,
    ) -> dict:
        """
        Create or update a product purchase for user.

        Args:
            telegram_id: Telegram user ID
            platform: Platform identifier
            product_id: Product ID
            purchase_price: Actual purchase price
            product_name: Product name
            purchase_date: Purchase date (ISO date or datetime)
            current_price: Current market price
            card_price: Card/wallet price
            avg_price: Average price from history
            original_price: Original price

        Returns:
            Saved purchase payload
        """
        if purchase_price <= 0:
            raise ValueError("purchase_price must be greater than 0")

        purchased_at = self._normalize_purchase_datetime(purchase_date)
        saved_vs_avg = self._calculate_saved_amount(avg_price, purchase_price)
        saved_vs_original = self._calculate_saved_amount(original_price, purchase_price)

        with self.db.get_connection() as conn:
            conn.execute(
                """INSERT INTO user_purchases (
                       telegram_id, platform, product_id, product_name,
                       purchase_price, current_price, card_price, avg_price,
                       original_price, saved_vs_avg, saved_vs_original,
                       purchased_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(telegram_id, platform, product_id) DO UPDATE SET
                       product_name = excluded.product_name,
                       purchase_price = excluded.purchase_price,
                       current_price = excluded.current_price,
                       card_price = excluded.card_price,
                       avg_price = excluded.avg_price,
                       original_price = excluded.original_price,
                       saved_vs_avg = excluded.saved_vs_avg,
                       saved_vs_original = excluded.saved_vs_original,
                       purchased_at = excluded.purchased_at,
                       updated_at = CURRENT_TIMESTAMP""",
                (
                    telegram_id,
                    platform,
                    product_id,
                    product_name,
                    purchase_price,
                    current_price,
                    card_price,
                    avg_price,
                    original_price,
                    saved_vs_avg,
                    saved_vs_original,
                    purchased_at,
                ),
            )

        logger.info(
            "Recorded purchase for user %s: %s:%s at %.2f",
            telegram_id,
            platform,
            product_id,
            purchase_price,
        )

        return {
            "telegram_id": telegram_id,
            "platform": platform,
            "product_id": product_id,
            "product_name": product_name,
            "purchase_price": self._round_money(purchase_price),
            "current_price": current_price,
            "card_price": card_price,
            "avg_price": avg_price,
            "original_price": original_price,
            "saved_vs_avg": saved_vs_avg,
            "saved_vs_original": saved_vs_original,
            "purchased_at": purchased_at,
        }

    def get_user_summary(self, telegram_id: int) -> dict:
        """
        Get user statistics summary.

        Args:
            telegram_id: Telegram user ID

        Returns:
            Dictionary with summary statistics
        """
        with self.db.get_connection() as conn:
            total_viewed = conn.execute(
                "SELECT COUNT(DISTINCT platform || product_id) as count FROM user_stats WHERE telegram_id = ?",
                (telegram_id,),
            ).fetchone()["count"]

            total_saved = conn.execute(
                "SELECT COALESCE(SUM(saved_amount), 0) as total FROM user_stats WHERE telegram_id = ?",
                (telegram_id,),
            ).fetchone()["total"]

            best_deal = conn.execute(
                """SELECT product_name, platform, product_id, price, card_price,
                          original_price, saved_amount
                   FROM user_stats
                   WHERE telegram_id = ? AND saved_amount > 0
                   ORDER BY saved_amount DESC LIMIT 1""",
                (telegram_id,),
            ).fetchone()

            month_start = datetime.now().replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
            monthly_views = conn.execute(
                """SELECT COUNT(*) as count FROM user_stats
                   WHERE telegram_id = ? AND created_at >= ?""",
                (telegram_id, month_start.isoformat()),
            ).fetchone()["count"]

            monthly_saved = conn.execute(
                """SELECT COALESCE(SUM(saved_amount), 0) as total FROM user_stats
                   WHERE telegram_id = ? AND created_at >= ?""",
                (telegram_id, month_start.isoformat()),
            ).fetchone()["total"]

            purchased_count = conn.execute(
                "SELECT COUNT(*) as count FROM user_purchases WHERE telegram_id = ?",
                (telegram_id,),
            ).fetchone()["count"]

            real_saved_total = conn.execute(
                """SELECT COALESCE(SUM(saved_vs_avg), 0) as total
                   FROM user_purchases
                   WHERE telegram_id = ?""",
                (telegram_id,),
            ).fetchone()["total"]

            return {
                "total_viewed": total_viewed,
                "total_saved": self._round_money(total_saved),
                "monthly_views": monthly_views,
                "monthly_saved": self._round_money(monthly_saved),
                "purchased_count": purchased_count,
                "real_saved_total": self._round_money(real_saved_total),
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
                """WITH latest_views AS (
                       SELECT us.platform,
                              us.product_id,
                              us.product_name,
                              us.price,
                              us.card_price,
                              us.avg_price,
                              us.original_price,
                              us.saved_amount,
                              us.created_at AS last_view
                       FROM user_stats us
                       INNER JOIN (
                           SELECT platform, product_id, MAX(id) AS latest_id
                           FROM user_stats
                           WHERE telegram_id = ? AND action = ?
                           GROUP BY platform, product_id
                       ) latest ON latest.latest_id = us.id
                       WHERE us.telegram_id = ?
                   )
                   SELECT lv.platform,
                          lv.product_id,
                          lv.product_name,
                          lv.price,
                          lv.card_price,
                          lv.avg_price,
                          lv.original_price,
                          lv.saved_amount,
                          lv.last_view,
                          up.purchase_price,
                          up.purchased_at
                   FROM latest_views lv
                   LEFT JOIN user_purchases up
                          ON up.telegram_id = ?
                         AND up.platform = lv.platform
                         AND up.product_id = lv.product_id
                   ORDER BY datetime(lv.last_view) DESC
                   LIMIT ?""",
                (telegram_id, self.VIEW_ACTION, telegram_id, telegram_id, limit),
            ).fetchall()

            return [dict(row) for row in rows]

    def get_user_purchases(self, telegram_id: int, limit: int = 50) -> list[dict]:
        """
        Get list of products purchased by user.

        Args:
            telegram_id: Telegram user ID
            limit: Maximum number of purchases to return

        Returns:
            List of purchase dictionaries
        """
        with self.db.get_connection() as conn:
            rows = conn.execute(
                """SELECT platform,
                          product_id,
                          product_name,
                          purchase_price,
                          current_price,
                          card_price,
                          avg_price,
                          original_price,
                          saved_vs_avg,
                          saved_vs_original,
                          purchased_at
                   FROM user_purchases
                   WHERE telegram_id = ?
                   ORDER BY datetime(purchased_at) DESC
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
