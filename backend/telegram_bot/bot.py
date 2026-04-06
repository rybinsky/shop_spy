"""
ShopSpy - Telegram Bot Module

Handles Telegram bot for price drop notifications.
"""

import asyncio
import logging
from typing import Optional

from aiogram import Bot, Dispatcher, types
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from backend.config import config
from backend.db import AlertsRepository, UsersRepository, get_database

logger = logging.getLogger(__name__)


class TelegramBot:
    """Telegram bot for price notifications."""

    def __init__(self):
        """Initialize bot with configuration."""
        self.token = config.telegram.bot_token
        self.enabled = config.telegram.enabled
        self.bot: Optional[Bot] = None
        self.dp: Optional[Dispatcher] = None

        # Repositories
        self.users_repo: Optional[UsersRepository] = None
        self.alerts_repo: Optional[AlertsRepository] = None

    def init_repos(self) -> None:
        """Initialize repositories after database is ready."""
        db = get_database()
        self.users_repo = UsersRepository(db)
        self.alerts_repo = AlertsRepository(db)

    async def start(self) -> None:
        """Start the bot if enabled."""
        if not self.enabled:
            logger.info("Telegram bot is disabled (no TELEGRAM_BOT_TOKEN)")
            return

        try:
            self.bot = Bot(token=self.token)
            self.dp = Dispatcher()
            self.init_repos()

            # Register handlers
            self._register_handlers()

            logger.info("Starting Telegram bot polling...")
            await self.dp.start_polling(self.bot)

        except Exception as e:
            logger.error(f"Failed to start Telegram bot: {e}")

    def _register_handlers(self) -> None:
        """Register command handlers."""

        @self.dp.message(Command("start"))
        async def cmd_start(message: types.Message):
            await self._handle_start(message)

        @self.dp.message(Command("stop"))
        async def cmd_stop(message: types.Message):
            await self._handle_stop(message)

        @self.dp.message(Command("list"))
        async def cmd_list(message: types.Message):
            await self._handle_list(message)

        @self.dp.message(Command("help"))
        async def cmd_help(message: types.Message):
            await self._handle_help(message)

    async def _handle_start(self, message: types.Message) -> None:
        """Handle /start command."""
        chat_id = message.chat.id
        username = message.from_user.username if message.from_user else None

        # Save user
        self.users_repo.save_user(chat_id, username)

        # Send welcome message
        text = f"""👋 Привет!

Я — <b>ShopSpy Bot</b>, помогаю следить за ценами на маркетплейсах.

📋 <b>Твой Chat ID:</b> <code>{chat_id}</code>

Используй этот ID на дашборде ShopSpy для привязки уведомлений.

<b>Команды:</b>
/start — показать это сообщение
/stop — отключить все уведомления
/list — мои отслеживаемые товары
/help — справка"""

        try:
            await message.answer(text, parse_mode="HTML")
            logger.info(f"User started bot: chat_id={chat_id}")
        except Exception as e:
            logger.error(f"Failed to send welcome message: {e}")

    async def _handle_stop(self, message: types.Message) -> None:
        """Handle /stop command."""
        chat_id = message.chat.id

        # Deactivate user and delete alerts
        self.users_repo.deactivate_user(chat_id)
        self.alerts_repo.delete_all_alerts_for_chat(chat_id)

        text = """✅ Уведомления отключены.

Чтобы снова включить, отправь /start"""

        try:
            await message.answer(text)
            logger.info(f"User stopped notifications: chat_id={chat_id}")
        except Exception as e:
            logger.error(f"Failed to send stop message: {e}")

    async def _handle_list(self, message: types.Message) -> None:
        """Handle /list command."""
        chat_id = message.chat.id
        alerts = self.alerts_repo.get_alerts_by_chat(chat_id)

        if not alerts:
            text = """📭 У тебя пока нет отслеживаемых товаров.

Добавь товары через дашборд ShopSpy:
1. Открой дашборд в браузере
2. Нажми "Отслеживать" на нужном товаре"""
            await message.answer(text)
            return

        text = "📋 <b>Отслеживаемые товары:</b>\n\n"

        for i, alert in enumerate(alerts[:10], 1):
            platform_emoji = "🟣" if alert["platform"] == "wb" else "🔵"
            name = alert.get("product_name") or alert["product_id"]
            if name and len(name) > 30:
                name = name[:30] + "..."

            target = (
                f"🎯 {alert['target_price']:,.0f} ₽"
                if alert.get("target_price")
                else ""
            )
            last = (
                f"Текущая: {alert['last_price']:,.0f} ₽"
                if alert.get("last_price")
                else ""
            )

            text += f"{i}. {platform_emoji} {name}\n   {target} {last}\n\n"

        if len(alerts) > 10:
            text += f"...и ещё {len(alerts) - 10} товаров"

        try:
            await message.answer(text, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Failed to send list: {e}")

    async def _handle_help(self, message: types.Message) -> None:
        """Handle /help command."""
        text = """🤖 <b>ShopSpy Bot — Справка</b>

<b>Как это работает:</b>
1. Установи расширение ShopSpy для Chrome
2. Открывай товары на WB или Ozon
3. На дашборде добавь товары в отслеживаемые
4. Укажи желаемую цену
5. Получай уведомления когда цена падает!

<b>Команды:</b>
/start — получить Chat ID
/stop — отключить уведомления
/list — мои товары
/help — эта справка

<b>Поддерживаемые площадки:</b>
🟣 Wildberries
🔵 Ozon"""

        try:
            await message.answer(text, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Failed to send help: {e}")

    async def send_price_alert(
        self,
        chat_id: int,
        product_name: str,
        old_price: float,
        new_price: float,
        url: Optional[str],
        platform: str,
    ) -> bool:
        """
        Send price change notification.

        Args:
            chat_id: Telegram chat ID
            product_name: Product name
            old_price: Previous price
            new_price: New price
            url: Product URL
            platform: Platform identifier ('wb' or 'ozon')

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.bot:
            return False

        platform_emoji = "🟣" if platform == "wb" else "🔵"
        platform_name = "Wildberries" if platform == "wb" else "Ozon"

        diff = new_price - old_price
        diff_percent = (diff / old_price) * 100 if old_price > 0 else 0

        if diff < 0:
            trend = "📉"
            trend_text = f"упала на {abs(diff_percent):.1f}% ({abs(diff):,.0f} ₽)"
        else:
            trend = "📈"
            trend_text = f"выросла на {diff_percent:.1f}% ({diff:,.0f} ₽)"

        # Truncate long names
        short_name = (
            product_name[:50] + "..." if len(product_name) > 50 else product_name
        )

        text = f"""{trend} <b>Изменение цены!</b>

{platform_emoji} <b>{platform_name}</b>
📦 {short_name}

💰 Старая цена: {old_price:,.0f} ₽
💰 Новая цена: <b>{new_price:,.0f} ₽</b>

{trend_text}"""

        keyboard = None
        if url:
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🛒 Открыть товар", url=url)]
                ]
            )

        try:
            await self.bot.send_message(
                chat_id,
                text,
                parse_mode="HTML",
                disable_web_page_preview=True,
                reply_markup=keyboard,
            )
            logger.info(f"Sent price alert to {chat_id}: {old_price} -> {new_price}")
            return True

        except TelegramForbiddenError:
            logger.warning(f"User {chat_id} blocked the bot")
            self.users_repo.deactivate_user(chat_id)
            return False

        except TelegramBadRequest as e:
            logger.error(f"Failed to send message to {chat_id}: {e}")
            return False

        except Exception as e:
            logger.error(f"Unexpected error sending to {chat_id}: {e}")
            return False

    async def send_target_reached_alert(
        self,
        chat_id: int,
        product_name: str,
        current_price: float,
        target_price: float,
        url: Optional[str],
        platform: str,
    ) -> bool:
        """
        Send target price reached notification.

        Args:
            chat_id: Telegram chat ID
            product_name: Product name
            current_price: Current price
            target_price: User's target price
            url: Product URL
            platform: Platform identifier

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.bot:
            return False

        platform_emoji = "🟣" if platform == "wb" else "🔵"
        platform_name = "Wildberries" if platform == "wb" else "Ozon"

        short_name = (
            product_name[:50] + "..." if len(product_name) > 50 else product_name
        )

        text = f"""🎯 <b>Целевая цена достигнута!</b>

{platform_emoji} <b>{platform_name}</b>
📦 {short_name}

💰 Текущая цена: <b>{current_price:,.0f} ₽</b>
🎯 Ваша цель: {target_price:,.0f} ₽

Самое время покупать! 🛍️"""

        keyboard = None
        if url:
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🛒 Открыть товар", url=url)]
                ]
            )

        try:
            await self.bot.send_message(
                chat_id,
                text,
                parse_mode="HTML",
                disable_web_page_preview=True,
                reply_markup=keyboard,
            )
            logger.info(f"Sent target alert to {chat_id}: reached {target_price}")
            return True

        except TelegramForbiddenError:
            logger.warning(f"User {chat_id} blocked the bot")
            self.users_repo.deactivate_user(chat_id)
            return False

        except Exception as e:
            logger.error(f"Failed to send target alert to {chat_id}: {e}")
            return False


# Global bot instance
telegram_bot = TelegramBot()


async def run_telegram_bot() -> None:
    """Run the Telegram bot (called from main)."""
    await telegram_bot.start()
