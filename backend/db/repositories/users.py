"""
ShopSpy - Users Repository

Database operations for Telegram users management.
"""

import logging
from typing import Optional

from backend.db.database import Database

logger = logging.getLogger(__name__)


# Data class for Telegram user info
class TelegramUserInfo:
    """Container for Telegram user information."""

    def __init__(
        self,
        telegram_id: int,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        username: Optional[str] = None,
        photo_url: Optional[str] = None,
    ):
        self.telegram_id = telegram_id
        self.first_name = first_name
        self.last_name = last_name
        self.username = username
        self.photo_url = photo_url


class UsersRepository:
    """Repository for Telegram users database operations."""

    def __init__(self, db: Database):
        """
        Initialize users repository.

        Args:
            db: Database instance
        """
        self.db = db

    def save_user(self, chat_id: int, username: Optional[str] = None) -> bool:
        """
        Save or update a Telegram user.

        Args:
            chat_id: Telegram Chat ID
            username: Telegram username

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.db.get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO telegram_users (chat_id, username, is_active)
                    VALUES (?, ?, TRUE)
                    ON CONFLICT(chat_id) DO UPDATE SET
                        username = excluded.username,
                        is_active = TRUE,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (chat_id, username),
                )
            logger.info(f"User saved: chat_id={chat_id}, username={username}")
            return True
        except Exception as e:
            logger.error(f"Failed to save user {chat_id}: {e}")
            return False

    def save_user_from_telegram_auth(
        self,
        telegram_id: int,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        username: Optional[str] = None,
        photo_url: Optional[str] = None,
    ) -> bool:
        """
        Save or update a user from Telegram Login Widget authentication.

        Args:
            telegram_id: Telegram user ID
            first_name: User's first name
            last_name: User's last name
            username: Telegram username
            photo_url: Profile photo URL

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.db.get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO telegram_users (chat_id, username, first_name, last_name, photo_url, is_active)
                    VALUES (?, ?, ?, ?, ?, TRUE)
                    ON CONFLICT(chat_id) DO UPDATE SET
                        username = excluded.username,
                        first_name = excluded.first_name,
                        last_name = excluded.last_name,
                        photo_url = excluded.photo_url,
                        is_active = TRUE,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (telegram_id, username, first_name, last_name, photo_url),
                )
            logger.info(
                f"User saved from Telegram auth: telegram_id={telegram_id}, username={username}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to save user from Telegram auth {telegram_id}: {e}")
            return False

    def get_user_by_telegram_id(self, telegram_id: int) -> Optional[dict]:
        """
        Get a user by Telegram ID.

        Args:
            telegram_id: Telegram user ID

        Returns:
            User dict or None if not found
        """
        with self.db.get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM telegram_users WHERE chat_id = ?",
                (telegram_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_user(self, chat_id: int) -> Optional[dict]:
        """
        Get a user by chat ID.

        Args:
            chat_id: Telegram Chat ID

        Returns:
            User dict or None if not found
        """
        with self.db.get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM telegram_users WHERE chat_id = ?",
                (chat_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def user_exists(self, chat_id: int) -> bool:
        """
        Check if a user exists.

        Args:
            chat_id: Telegram Chat ID

        Returns:
            True if user exists, False otherwise
        """
        return self.get_user(chat_id) is not None

    def is_active(self, chat_id: int) -> bool:
        """
        Check if a user is active.

        Args:
            chat_id: Telegram Chat ID

        Returns:
            True if user is active, False otherwise
        """
        user = self.get_user(chat_id)
        return user.get("is_active", False) if user else False

    def deactivate_user(self, chat_id: int) -> bool:
        """
        Deactivate a user (stop notifications).

        Args:
            chat_id: Telegram Chat ID

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.db.get_connection() as conn:
                conn.execute(
                    """
                    UPDATE telegram_users
                    SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
                    WHERE chat_id = ?
                    """,
                    (chat_id,),
                )
            logger.info(f"User deactivated: chat_id={chat_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to deactivate user {chat_id}: {e}")
            return False

    def activate_user(self, chat_id: int) -> bool:
        """
        Activate a user.

        Args:
            chat_id: Telegram Chat ID

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.db.get_connection() as conn:
                conn.execute(
                    """
                    UPDATE telegram_users
                    SET is_active = TRUE, updated_at = CURRENT_TIMESTAMP
                    WHERE chat_id = ?
                    """,
                    (chat_id,),
                )
            logger.info(f"User activated: chat_id={chat_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to activate user {chat_id}: {e}")
            return False

    def get_all_active_chat_ids(self) -> list[int]:
        """
        Get all active user chat IDs.

        Returns:
            List of active chat IDs
        """
        with self.db.get_cursor() as cursor:
            cursor.execute("SELECT chat_id FROM telegram_users WHERE is_active = TRUE")
            return [row["chat_id"] for row in cursor.fetchall()]

    def get_all_users(self) -> list[dict]:
        """
        Get all users (for admin panel).

        Returns:
            List of all user dictionaries
        """
        with self.db.get_cursor() as cursor:
            cursor.execute(
                """
                SELECT chat_id, username, first_name, last_name, photo_url,
                       is_active, created_at, updated_at
                FROM telegram_users
                ORDER BY created_at DESC
                """
            )
            return [dict(row) for row in cursor.fetchall()]

    def count_active_users(self) -> int:
        """
        Count active users.

        Returns:
            Number of active users
        """
        with self.db.get_cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) as count FROM telegram_users WHERE is_active = TRUE"
            )
            result = cursor.fetchone()
            return result["count"] if result else 0

    def delete_user(self, chat_id: int) -> bool:
        """
        Delete a user completely.

        Args:
            chat_id: Telegram Chat ID

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.db.get_connection() as conn:
                conn.execute(
                    "DELETE FROM telegram_users WHERE chat_id = ?",
                    (chat_id,),
                )
            logger.info(f"User deleted: chat_id={chat_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete user {chat_id}: {e}")
            return False
