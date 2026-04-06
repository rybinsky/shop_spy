"""
ShopSpy - Database Module

Database connection management and repositories.
"""

from backend.db.database import Database, get_database, init_database
from backend.db.repositories.alerts import AlertsRepository
from backend.db.repositories.prices import PricesRepository
from backend.db.repositories.users import UsersRepository

__all__ = [
    "Database",
    "get_database",
    "init_database",
    "PricesRepository",
    "AlertsRepository",
    "UsersRepository",
]
