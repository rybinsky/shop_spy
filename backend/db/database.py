"""
ShopSpy - Database Connection Module

Handles SQLite database connections, initialization, and connection pooling.
"""

import logging
import os
import sqlite3
from contextlib import contextmanager
from typing import Generator, Optional

logger = logging.getLogger(__name__)


class Database:
    """SQLite database connection manager."""

    def __init__(self, db_path: str):
        """
        Initialize database manager.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._ensure_directory()

    def _ensure_directory(self) -> None:
        """Ensure database directory exists."""
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
            logger.debug(f"Database directory ensured: {db_dir}")

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Get a database connection as a context manager.

        Yields:
            sqlite3.Connection: Database connection

        Example:
            with db.get_connection() as conn:
                conn.execute("SELECT * FROM prices")
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()

    @contextmanager
    def get_cursor(self) -> Generator[sqlite3.Cursor, None, None]:
        """
        Get a database cursor as a context manager.

        Yields:
            sqlite3.Cursor: Database cursor
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                yield cursor
            finally:
                cursor.close()

    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """
        Execute a single query.

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            Cursor with results
        """
        with self.get_connection() as conn:
            return conn.execute(query, params)

    def executescript(self, script: str) -> None:
        """
        Execute multiple SQL statements.

        Args:
            script: SQL script with multiple statements
        """
        with self.get_connection() as conn:
            conn.executescript(script)
            logger.debug("Executed SQL script successfully")

    def init_tables(self) -> None:
        """Initialize all required database tables."""
        self.executescript(
            """
            -- Price history table
            CREATE TABLE IF NOT EXISTS prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                product_id TEXT NOT NULL,
                product_name TEXT,
                price REAL NOT NULL,
                original_price REAL,
                card_price REAL,
                url TEXT,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_prices_product
            ON prices(platform, product_id);

            CREATE INDEX IF NOT EXISTS idx_prices_recorded_at
            ON prices(recorded_at);

            -- Reviews analysis cache
            CREATE TABLE IF NOT EXISTS reviews_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                product_id TEXT NOT NULL,
                summary TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_reviews_product
            ON reviews_cache(platform, product_id);

            -- Telegram users
            CREATE TABLE IF NOT EXISTS telegram_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                photo_url TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_telegram_users_active
            ON telegram_users(is_active);

            -- Price alerts
            CREATE TABLE IF NOT EXISTS price_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                platform TEXT NOT NULL,
                product_id TEXT NOT NULL,
                product_name TEXT,
                target_price REAL,
                last_price REAL,
                url TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (chat_id) REFERENCES telegram_users(chat_id)
                    ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_alerts_chat
            ON price_alerts(chat_id, is_active);

            CREATE INDEX IF NOT EXISTS idx_alerts_product
            ON price_alerts(platform, product_id, is_active);

            -- User statistics (views, savings)
            CREATE TABLE IF NOT EXISTS user_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                platform TEXT NOT NULL,
                product_id TEXT NOT NULL,
                product_name TEXT,
                price REAL,
                card_price REAL,
                avg_price REAL,
                original_price REAL,
                saved_amount REAL DEFAULT 0,
                action TEXT DEFAULT 'view',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_user_stats_telegram
            ON user_stats(telegram_id);

            CREATE INDEX IF NOT EXISTS idx_user_stats_product
            ON user_stats(telegram_id, platform, product_id);

            CREATE INDEX IF NOT EXISTS idx_user_stats_created
            ON user_stats(telegram_id, created_at);
        """
        )
        # Migration: Add card_price column if it doesn't exist
        try:
            with self.get_connection() as conn:
                conn.execute("ALTER TABLE prices ADD COLUMN card_price REAL")
                logger.info("Added card_price column to prices table")
        except Exception:
            # Column already exists, ignore
            pass

        logger.info("Database tables initialized successfully")

    def table_exists(self, table_name: str) -> bool:
        """
        Check if a table exists in the database.

        Args:
            table_name: Name of the table to check

        Returns:
            True if table exists, False otherwise
        """
        with self.get_cursor() as cursor:
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,),
            )
            return cursor.fetchone() is not None

    def get_table_count(self, table_name: str) -> int:
        """
        Get the number of rows in a table.

        Args:
            table_name: Name of the table

        Returns:
            Number of rows
        """
        with self.get_cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*) as count FROM {table_name}")
            result = cursor.fetchone()
            return result["count"] if result else 0


# Global database instance (initialized later with config)
_db: Optional[Database] = None


def init_database(db_path: str) -> Database:
    """
    Initialize the global database instance.

    Args:
        db_path: Path to SQLite database file

    Returns:
        Database instance
    """
    global _db
    _db = Database(db_path)
    _db.init_tables()
    logger.info(f"Database initialized at: {db_path}")
    return _db


def get_database() -> Database:
    """
    Get the global database instance.

    Returns:
        Database instance

    Raises:
        RuntimeError: If database not initialized
    """
    if _db is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    return _db
