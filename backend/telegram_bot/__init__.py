"""
ShopSpy - Telegram Bot Module

Telegram bot for price drop notifications.
"""

from backend.telegram_bot.bot import TelegramBot, telegram_bot

__all__ = ["TelegramBot", "telegram_bot", "get_bot"]


def get_bot():
    """
    Get the Telegram bot instance.

    Returns:
        TelegramBot instance or None if not initialized
    """
    return telegram_bot.bot if telegram_bot else None
