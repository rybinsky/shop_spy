"""
ShopSpy - Telegram Bot Module

Handles Telegram bot for price drop notifications.
"""

import logging
from typing import Optional

from aiogram import Bot, Dispatcher, types
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

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

    def _get_main_keyboard(self) -> ReplyKeyboardMarkup:
        """Get main menu keyboard."""
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📋 Мои товары")],
                [KeyboardButton(text="❓ Помощь"), KeyboardButton(text="🚫 Отключить")],
            ],
            resize_keyboard=True,
            one_time_keyboard=False,
        )
        return keyboard

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

        # Handle button presses
        @self.dp.message(lambda m: m.text == "📋 Мои товары")
        async def btn_list(message: types.Message):
            await self._handle_list(message)

        @self.dp.message(lambda m: m.text == "❓ Помощь")
        async def btn_help(message: types.Message):
            await self._handle_help(message)

        @self.dp.message(lambda m: m.text == "🚫 Отключить")
        async def btn_stop(message: types.Message):
            await self._handle_stop(message)

        # Handle callback queries (inline buttons)
        @self.dp.callback_query(lambda c: c.data.startswith("delete_"))
        async def callback_delete(callback: CallbackQuery):
            await self._handle_delete_callback(callback)

    async def _handle_start(self, message: types.Message) -> None:
        """Handle /start command."""
        chat_id = message.chat.id
        username = message.from_user.username if message.from_user else None

        # Save user
        self.users_repo.save_user(chat_id, username)

        # Send welcome message with keyboard
        text = f"""👋 Привет!

Я — <b>ShopSpy Bot</b>, помогаю следить за ценами на маркетплейсах.

📋 <b>Твой Chat ID:</b> <code>{chat_id}</code>

Используй этот ID в расширении ShopSpy для привязки уведомлений.

<b>Как пользоваться:</b>
1️⃣ Установи расширение ShopSpy для Chrome
2️⃣ Открой товар на WB или Ozon
3️⃣ Нажми "Отслеживать" в панели ShopSpy
4️⃣ Получай уведомления о смене цены!

Используй кнопки ниже для управления 👇"""

        try:
            await message.answer(
                text, parse_mode="HTML", reply_markup=self._get_main_keyboard()
            )
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
            await message.answer(text, reply_markup=self._get_main_keyboard())
            logger.info(f"User stopped notifications: chat_id={chat_id}")
        except Exception as e:
            logger.error(f"Failed to send stop message: {e}")

    async def _handle_delete_callback(self, callback: CallbackQuery) -> None:
        """Handle delete button callback."""
        chat_id = callback.message.chat.id

        # Parse callback data: delete_platform_productId
        try:
            parts = callback.data.split("_")
            if len(parts) < 3:
                await callback.answer("Ошибка: неверные данные")
                return

            platform = parts[1]
            product_id = parts[2]

            # Delete the alert
            success = self.alerts_repo.delete_alert(chat_id, platform, product_id)

            if success:
                # Edit the message to show it's deleted
                try:
                    await callback.message.edit_text(
                        "❌ Товар удалён из отслеживания", reply_markup=None
                    )
                except Exception:
                    pass
                await callback.answer("✅ Товар удалён")
                logger.info(f"Deleted alert: {platform}:{product_id} for {chat_id}")
            else:
                await callback.answer("Ошибка при удалении")

        except Exception as e:
            logger.error(f"Error handling delete callback: {e}")
            await callback.answer("Произошла ошибка")

    async def _handle_list(self, message: types.Message) -> None:
        """Handle /list command."""
        chat_id = message.chat.id
        alerts = self.alerts_repo.get_alerts_by_chat(chat_id)

        if not alerts:
            text = """📭 У тебя пока нет отслеживаемых товаров.

Добавь товары через расширение ShopSpy:
1. Открой товар на WB или Ozon
2. Нажми "Отслеживать" в панели ShopSpy"""
            await message.answer(text, reply_markup=self._get_main_keyboard())
            return

        # Send each product as separate message with button
        for i, alert in enumerate(alerts, 1):
            platform_emoji = "🟣" if alert["platform"] == "wb" else "🔵"
            platform_name = "Wildberries" if alert["platform"] == "wb" else "Ozon"
            name = alert.get("product_name") or alert["product_id"]

            # Make product name a clickable link if URL is available
            if alert.get("url"):
                name_display = f'<a href="{alert["url"]}">{name}</a>'
            else:
                name_display = name

            price_info = ""
            if alert.get("last_price"):
                price_info = f"\n💰 Цена: <b>{alert['last_price']:,.0f} ₽</b>"

            text = f"""{i}. {platform_emoji} <b>{platform_name}</b>
📦 {name_display}{price_info}"""

            # Create inline keyboard
            buttons = []
            if alert.get("url"):
                buttons.append(
                    [InlineKeyboardButton(text="🛒 Открыть товар", url=alert["url"])]
                )
            buttons.append(
                [
                    InlineKeyboardButton(
                        text="❌ Удалить",
                        callback_data=f"delete_{alert['platform']}_{alert['product_id']}",
                    )
                ]
            )
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

            try:
                await message.answer(
                    text,
                    parse_mode="HTML",
                    reply_markup=keyboard,
                    disable_web_page_preview=True,
                )
            except Exception as e:
                logger.error(f"Failed to send product {i}: {e}")

        # Summary message
        total_text = f"\n📊 Всего товаров: {len(alerts)}"
        await message.answer(total_text, reply_markup=self._get_main_keyboard())

    async def _handle_help(self, message: types.Message) -> None:
        """Handle /help command."""
        text = """🤖 <b>ShopSpy Bot — Справка</b>

<b>Как это работает:</b>
1️⃣ Установи расширение ShopSpy для Chrome
2️⃣ Открой товар на WB или Ozon
3️⃣ Нажми "Отслеживать" в панели ShopSpy
4️⃣ Получай уведомления о любой смене цены!

<b>Кнопки меню:</b>
📋 Мои товары — список отслеживаемых
❓ Помощь — эта справка
🚫 Отключить — отключить все уведомления

<b>Поддерживаемые площадки:</b>
🟣 Wildberries
🔵 Ozon

<b>Дополнительно:</b>
• Уведомления приходят автоматически при смене цены
• Crawler проверяет цены каждые 6 часов"""

        try:
            await message.answer(
                text, parse_mode="HTML", reply_markup=self._get_main_keyboard()
            )
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

        text = f"""{trend} <b>Изменение цены!</b>

{platform_emoji} <b>{platform_name}</b>
📦 {product_name}

💰 Было: {old_price:,.0f} ₽
💰 Стало: <b>{new_price:,.0f} ₽</b>

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

        text = f"""🎯 <b>Целевая цена достигнута!</b>

{platform_emoji} <b>{platform_name}</b>
📦 {product_name}

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
