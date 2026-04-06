"""
ShopSpy Backend Package

AI-powered price tracking assistant for Russian marketplaces.
"""

from backend.config import Config, config
from backend.db import Database, get_database, init_database

__all__ = [
    "config",
    "Config",
    "Database",
    "get_database",
    "init_database",
]
