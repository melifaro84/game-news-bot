"""
Telegram bot module for sending news as rich posts with AI-generated summaries
"""
import asyncio
import io
import logging
import os
from datetime import datetime
from typing import Optional

import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.session.aiohttp import AiohttpSession

from config import config
from news_fetcher import NewsItem
from post_publisher import PostPublisher, PostContent

logger = logging.getLogger(__name__)


class TelegramNewsBot:
    """Bot for sending game news as rich posts to Telegram"""

    def __init__(self, ai_api_key: str = ""):
        self.bot: Optional[Bot] = None
        self.dp: Optional[Dispatcher] = None
        self._configured = False
        self.ai_api_key = ai_api_key
        self._post_publisher: Optional[PostPublisher] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._scheduler_ref = None  # Reference to scheduler for commands

    @property
    def post_publisher(self) -> PostPublisher:
        """Lazy initialization of post publisher"""
        if self._post_publisher is None:
            self._post_publisher = PostPublisher(self.ai_api_key)
        return self._post_publisher

    def configure(self) -> bool:
        """
        Initialize the bot with configuration.
        Returns True if configured successfully.
        """
        if not config.telegram.is_configured():
            logger.error("Telegram bot not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")
            return False

        try:
            # Proxy configuration
            proxy_url = os.environ.get('SOCKS5_PROXY', None)
            
            if proxy_url:
                logger.info(f"Using proxy: {proxy_url}")
                session = AiohttpSession(proxy=proxy_url)
                self.bot = Bot(
                    token=config.telegram.bot_token,
                    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
                    session=session
                )
            else:
                self.bot = Bot(
                    token=config.telegram.bot_token,
                    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
                )
            
            self.dp = Dispatcher()
            self._configured = True
            logger.info("Telegram bot configured successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to configure Telegram bot: {e}")
            return False

    async def send_news_posts(self, news: list[NewsItem]) -> int:
        """
        Send news as individual posts with AI-generated summaries.
        Each news item becomes a separate post.

        Args:
            news: List of NewsItem to send

        Returns:
            Number of successfully sent posts
        """
        if not self._configured:
            logger.error("Bot not configured")
            return 0

        if not news:
            logger.warning("No news to send")
            return 0

        sent_count = 0
        
        # Send each news item as a separate post
        for i, item in enumerate(news, 1):
            try:
                # Prepare the post content with AI summary
                post = await self.post_publisher.prepare_post(item)
                
                # Send as post with optional image
                success = await self._send_post(post)
                
                if success:
                    sent_count += 1
                    logger.info(f"Sent post {i}/{len(news)}: {item.title[:50]}...")
                else:
                    logger.warning(f"Failed to send post {i}/{len(news)}")
                
                # Small delay to avoid rate limiting
                import asyncio
                await asyncio.sleep(1.5)  # Longer delay for AI processing
                
            except Exception as e:
                logger.error(f"Error sending post {i}: {e}")

        logger.info(f"Successfully sent {sent_count} posts")
        return sent_count

    async def _send_post(self, post: PostContent) -> bool:
        """Send a single post with optional image and source link"""
        if not self.bot:
            return False

        # Add source link at the end
        source_link = f"\n\n📎 <a href='{post.source_url}'>Источник</a>"
        full_text = post.summary + source_link

        try:
            if post.image_url:
                # Try to send with image - download first (longer timeout)
                try:
                    import aiohttp
                    from aiogram.types import BufferedInputFile
                    
                    timeout = aiohttp.ClientTimeout(total=60)
                    async with aiohttp.ClientSession(timeout=timeout) as session:
                        async with session.get(post.image_url) as resp:
                            if resp.status == 200:
                                img_data = await resp.read()
                                photo_file = BufferedInputFile(img_data, filename='image.jpg')
                                
                                await self.bot.send_photo(
                                    chat_id=config.telegram.chat_id,
                                    photo=photo_file,
                                    caption=full_text,
                                    parse_mode=ParseMode.HTML
                                )
                                return True
                except Exception as img_err:
                    logger.warning(f"Failed to download image: {img_err}")
                
                # Fallback: try with URL directly (no download needed)
                try:
                    await self.bot.send_photo(
                        chat_id=config.telegram.chat_id,
                        photo=post.image_url,
                        caption=full_text,
                        parse_mode=ParseMode.HTML
                    )
                    return True
                except TelegramAPIError as e:
                    logger.warning(f"Failed to send photo URL: {e}")
                    # Fall back to text only
                    await self.bot.send_message(
                        chat_id=config.telegram.chat_id,
                        text=full_text,
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=False
                    )
                    return True
            else:
                # Send text only
                await self.bot.send_message(
                    chat_id=config.telegram.chat_id,
                    text=full_text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=False
                )
                return True
                
        except TelegramAPIError as e:
            logger.error(f"Failed to send post: {e}")
            return False

    async def _send_text(self, text: str) -> bool:
        """Send text message to chat"""
        if not self.bot:
            return False

        try:
            await self.bot.send_message(
                chat_id=config.telegram.chat_id,
                text=text,
                disable_web_page_preview=True
            )
            return True
        except TelegramAPIError as e:
            logger.error(f"Failed to send message: {e}")
            return False

    def _format_header(self, news_count: int) -> str:
        """Format digest header"""
        now = datetime.now().strftime("%d.%m.%Y")
        return (
            f"🎮 <b>Игровые новости</b> · {now}\n"
        )

    async def send_test_message(self, text: str = "✅ Бот работает! Тестовое сообщение.") -> bool:
        """Send a test message to verify configuration"""
        return await self._send_text(text)

    async def close(self):
        """Close bot session and cleanup"""
        if self._post_publisher:
            self._post_publisher.close()
        if self.bot:
            await self.bot.session.close()

    def setup_handlers(self, scheduler=None):
        """Setup command handlers"""
        if not self.dp:
            return
        
        self._scheduler_ref = scheduler
        dp = self.dp
        
        # Кнопки меню
        menu_keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📊 Статус")],
                [KeyboardButton(text="📤 Отправить сейчас")],
                [KeyboardButton(text="📡 Источники")],
                [KeyboardButton(text="⏰ Расписание")],
            ],
            resize_keyboard=True
        )
        
        inline_menu = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Статус", callback_data="cmd_status")],
            [InlineKeyboardButton(text="📤 Отправить сейчас", callback_data="cmd_send")],
            [InlineKeyboardButton(text="📡 Источники", callback_data="cmd_sources")],
        ])
        
        @dp.message(Command("start"))
        async def cmd_start(message: Message):
            text = (
                "🎮 <b>Game News Bot</b>\n\n"
                "Автоматический агрегатор новостей о ретро-играх и портативных консолях.\n\n"
                "<b>Команды:</b>\n"
                "• /start - это меню\n"
                "• /status - статус бота\n"
                "• /send - отправить новости сейчас\n"
                "• /sources - список источников\n"
                "• /schedule - расписание\n"
                "• /test - тестовое сообщение\n"
            )
            await message.answer(text, reply_markup=menu_keyboard)
        
        @dp.message(Command("help"))
        async def cmd_help(message: Message):
            await cmd_start(message)
        
        @dp.message(Command("status"))
        async def cmd_status(message: Message):
            sent_count = 0
            try:
                with open('.sent_hashes', 'r') as f:
                    sent_count = len(f.readlines())
            except:
                pass
            
            next_run = "Неизвестно"
            if self._scheduler_ref:
                next_run = self._scheduler_ref.get_next_run()
            
            text = (
                f"📊 <b>Статус бота</b>\n\n"
                f"• Работает: ✅ Да\n"
                f"• Отправлено новостей: {sent_count}\n"
                f"• Следующая отправка: {next_run}\n"
            )
            await message.answer(text)
        
        @dp.message(Command("send"))
        @dp.message(F.text == "📤 Отправить сейчас")
        async def cmd_send(message: Message):
            await message.answer("⏳ Запускаю сбор и отправку новостей...")
            if self._scheduler_ref:
                await self._scheduler_ref.fetch_and_send_news()
                await message.answer("✅ Новости отправлены!")
            else:
                await message.answer("❌ Планировщик недоступен")
        
        @dp.message(Command("sources"))
        @dp.message(F.text == "📡 Источники")
        async def cmd_sources(message: Message):
            sources_text = "📡 <b>Источники новостей:</b>\n\n"
            for src in config.sources.news:
                status = "✅" if src.get('enabled', True) else "❌"
                name = src.get('name', 'Unknown')
                cat = src.get('category', '')
                sources_text += f"{status} {name} ({cat})\n"
            
            sources_text += "\n<i>Новости берутся автоматически и фильтруются по ключевым словам.</i>"
            await message.answer(sources_text)
        
        @dp.message(Command("schedule"))
        @dp.message(F.text == "⏰ Расписание")
        async def cmd_schedule(message: Message):
            text = (
                "⏰ <b>Расписание отправок</b>\n\n"
                "• 07:00 — Утренняя подборка\n"
                "• 8:30 — 2 новости\n"
                "• 10:30 — 2 новости\n"
                "• 11:30 — 2 новости\n"
                "• 13:30 — 2 новости\n"
                "• 14:30 — 2 новости\n"
                "• 16:30 — 2 новости\n"
                "• 17:30 — 2 новости\n"
                "• 19:30 — 2 новости\n"
                "• 20:30 — 2 новости\n"
                "• 22:30 — 2 новости\n\n"
                "📝 Всего: до 24 новостей в день\n"
                "🔄 Дубликаты自动но исключаются"
            )
            await message.answer(text)
        
        @dp.message(Command("test"))
        async def cmd_test(message: Message):
            await message.answer("✅ Тест: Бот работает!")
        
        @dp.message(F.text == "📊 Статус")
        async def btn_status(message: Message):
            await cmd_status(message)
        
        @dp.message(F.text == "⏰ Расписание")
        async def btn_schedule(message: Message):
            await cmd_schedule(message)
        
        logger.info("Telegram handlers setup complete")

    async def start_polling(self):
        """Start bot in polling mode for commands with auto-reconnect"""
        if not self._configured:
            logger.error("Cannot start polling: bot not configured")
            return
        
        logger.info("Starting bot polling for commands...")
        retry_count = 0
        max_retries = 100
        
        from aiogram.client.default import DefaultBotProperties
        from aiogram.methods import GetMe
        
        # Test connection first
        try:
            await self.bot.session.storage.get_me()
            logger.info("Telegram connection OK")
        except Exception as e:
            logger.warning(f"Telegram connection test failed: {e}")
        
        while retry_count < max_retries:
            try:
                # Start polling with longer timeout
                await self.dp.start_polling(
                    self.bot,
                    timeout=60,  # 60 seconds timeout
                    handle_as_tasks=True
                )
                break  # Normal exit
            except asyncio.CancelledError:
                logger.info("Polling cancelled")
                break
            except Exception as e:
                retry_count += 1
                logger.warning(f"Polling error (attempt {retry_count}): {e}")
                await asyncio.sleep(10)  # Wait longer before reconnect
        
        if retry_count >= max_retries:
            logger.error("Max polling retries reached, giving up")
