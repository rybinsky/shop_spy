"""
ShopSpy - Alerts Repository

Database operations for price alerts management.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class AlertsRepository:
    """Repository for price alerts database operations."""

    def __init__(self, database):
        """
        Initialize alerts repository.

        Args:
            database: Database instance with connection management
        """
        self.db = database

    def create_alert(
        self,
        chat_id: int,
        platform: str,
        product_id: str,
        product_name: Optional[str] = None,
        target_price: Optional[float] = None,
        url: Optional[str] = None,
    ) -> bool:
        """
        Create or update a price alert.

        Args:
            chat_id: Telegram chat ID
            platform: Platform identifier ('wb' or 'ozon')
            product_id: Product ID on the platform
            product_name: Product name
            target_price: Target price for notification
            url: Product URL

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.db.get_connection() as conn:
                # Check if alert already exists
                existing = conn.execute(
                    """
                    SELECT id FROM price_alerts
                    WHERE chat_id = ? AND platform = ? AND product_id = ? AND is_active = TRUE
                    """,
                    (chat_id, platform, product_id),
                ).fetchone()

                if existing:
                    # Update existing alert
                    conn.execute(
                        """
                        UPDATE price_alerts
                        SET product_name = ?, target_price = ?, url = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        (product_name, target_price, url, existing["id"]),
                    )
                    logger.debug(
                        f"Updated alert for {platform}:{product_id} (chat_id={chat_id})"
                    )
                else:
                    # Create new alert
                    conn.execute(
                        """
                        INSERT INTO price_alerts
                        (chat_id, platform, product_id, product_name, target_price, url)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            chat_id,
                            platform,
                            product_id,
                            product_name,
                            target_price,
                            url,
                        ),
                    )
                    logger.info(
                        f"Created alert for {platform}:{product_id} (chat_id={chat_id})"
                    )
            return True
        except Exception as e:
            logger.error(f"Error creating alert: {e}")
            return False

    def get_alerts_by_chat(self, chat_id: int) -> list[dict]:
        """
        Get all active alerts for a user.

        Args:
            chat_id: Telegram chat ID

        Returns:
            List of alert dictionaries
        """
        try:
            with self.db.get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT platform, product_id, product_name, target_price,
                           last_price, url, created_at
                    FROM price_alerts
                    WHERE chat_id = ? AND is_active = TRUE
                    ORDER BY created_at DESC
                    """,
                    (chat_id,),
                ).fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting alerts for chat {chat_id}: {e}")
            return []

    def get_alerts_by_product(self, platform: str, product_id: str) -> list[dict]:
        """
        Get all active alerts for a specific product.

        Args:
            platform: Platform identifier
            product_id: Product ID

        Returns:
            List of alert dictionaries with chat_id
        """
        try:
            with self.db.get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT a.chat_id, a.product_name, a.target_price, a.last_price, a.url
                    FROM price_alerts a
                    INNER JOIN telegram_users u ON a.chat_id = u.chat_id
                    WHERE a.platform = ? AND a.product_id = ?
                      AND a.is_active = TRUE AND u.is_active = TRUE
                    """,
                    (platform, product_id),
                ).fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(
                f"Error getting alerts for product {platform}:{product_id}: {e}"
            )
            return []

    def update_last_price(
        self,
        chat_id: int,
        platform: str,
        product_id: str,
        price: float,
    ) -> bool:
        """
        Update the last known price for an alert.

        Args:
            chat_id: Telegram chat ID
            platform: Platform identifier
            product_id: Product ID
            price: Current price

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.db.get_connection() as conn:
                conn.execute(
                    """
                    UPDATE price_alerts
                    SET last_price = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE chat_id = ? AND platform = ? AND product_id = ? AND is_active = TRUE
                    """,
                    (price, chat_id, platform, product_id),
                )
            return True
        except Exception as e:
            logger.error(f"Error updating last price: {e}")
            return False

    def delete_alert(self, chat_id: int, platform: str, product_id: str) -> bool:
        """
        Soft delete an alert (mark as inactive).

        Args:
            chat_id: Telegram chat ID
            platform: Platform identifier
            product_id: Product ID

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.db.get_connection() as conn:
                conn.execute(
                    """
                    UPDATE price_alerts
                    SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
                    WHERE chat_id = ? AND platform = ? AND product_id = ?
                    """,
                    (chat_id, platform, product_id),
                )
            logger.info(
                f"Deleted alert for {platform}:{product_id} (chat_id={chat_id})"
            )
            return True
        except Exception as e:
            logger.error(f"Error deleting alert: {e}")
            return False

    def delete_all_alerts_for_chat(self, chat_id: int) -> bool:
        """
        Soft delete all alerts for a user.

        Args:
            chat_id: Telegram chat ID

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.db.get_connection() as conn:
                conn.execute(
                    """
                    UPDATE price_alerts
                    SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
                    WHERE chat_id = ?
                    """,
                    (chat_id,),
                )
            logger.info(f"Deleted all alerts for chat_id={chat_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting all alerts: {e}")
            return False

    def count_active_alerts(self) -> int:
        """
        Count total active alerts.

        Returns:
            Number of active alerts
        """
        try:
            with self.db.get_connection() as conn:
                row = conn.execute(
                    "SELECT COUNT(*) as count FROM price_alerts WHERE is_active = TRUE"
                ).fetchone()
                return row["count"] if row else 0
        except Exception as e:
            logger.error(f"Error counting alerts: {e}")
            return 0
