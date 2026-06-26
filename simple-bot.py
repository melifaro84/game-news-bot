#!/usr/bin/env python3
"""
Simple News Bot - автоматическая рассылка + обработка команд Telegram
"""
import asyncio
import logging
import sys
import os
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from config import config
from news_fetcher import NewsFetcher
from telegram_bot import TelegramNewsBot
from post_publisher import PostPublisher

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('simple-bot.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


class SimpleNewsBot:
    def __init__(self):
        self.news_fetcher = NewsFetcher(lookback_hours=24)
        self.bot = TelegramNewsBot(config.telegram.deepseek_api_key)
        self.publisher = PostPublisher(config.telegram.deepseek_api_key)
        self.sent_hashes = self._load_sent_hashes()
        self.scheduler_task = None
        self.polling_task = None
        
    def _load_sent_hashes(self):
        try:
            with open('.sent_hashes', 'r') as f:
                return set(line.strip() for line in f if line.strip())
        except:
            return set()
    
    def _save_sent_hashes(self):
        with open('.sent_hashes', 'w') as f:
            for h in self.sent_hashes:
                f.write(h + '\n')
    
    def _get_hash(self, title, link):
        import hashlib
        return hashlib.md5(f"{title.lower()}|{link.lower()}".encode()).hexdigest()
    
    async def send_news(self, count=2):
        """Отправить N новостей"""
        logger.info("Fetching news...")
        all_news = self.news_fetcher.get_all_news(max_per_source=5)
        
        # Фильтр дубликатов
        unique = []
        for n in all_news:
            h = self._get_hash(n.title, n.link)
            if h not in self.sent_hashes:
                unique.append(n)
                self.sent_hashes.add(h)
        
        if not unique:
            logger.info("No new news")
            await self.bot._send_text("ℹ️ Новых новостей нет.")
            return 0
        
        # Берём из разных источников
        import random
        random.shuffle(unique)
        
        selected = []
        used_sources = set()
        for n in unique:
            if n.source not in used_sources and len(selected) < count:
                selected.append(n)
                used_sources.add(n.source)
        
        if len(selected) < count:
            selected = unique[:count]
        
        self._save_sent_hashes()
        
        # Отправляем
        sent = 0
        for n in selected:
            logger.info(f"Sending: {n.title[:50]}...")
            post = await self.publisher.prepare_post(n)
            if post:
                if await self.bot._send_post(post):
                    sent += 1
            await asyncio.sleep(2)
        
        logger.info(f"Sent {sent} posts")
        return sent
    
    async def scheduler_loop(self):
        """Автоматическая рассылка по расписанию"""
        logger.info("Scheduler started!")
        last_send_key = None
        
        while True:
            try:
                now = datetime.now()
                hour = now.hour
                minute = now.minute
                
                # Расписание: 07:00 (утро), 8:30, 10:30, 11:30, 13:30, 14:30, 16:30, 17:30, 19:30, 20:30, 22:30
                schedule = [(7, 0), (8, 30), (10, 30), (11, 30), (13, 30), (14, 30), 
                           (16, 30), (17, 30), (19, 30), (20, 30), (22, 30)]
                
                for h, m in schedule:
                    if h == hour and abs(minute - m) < 5:
                        send_key = (h, m)
                        if send_key != last_send_key:
                            last_send_key = send_key
                            count = 10 if h == 7 else 2  # Утром 10 новостей
                            logger.info(f"Scheduled send at {h}:{m} ({count} news)")
                            
                            if h == 7:
                                # Утренняя подборка - берём больше новостей
                                await self.send_morning_digest()
                            else:
                                await self.send_news(2)
                        break
                
                await asyncio.sleep(60)
                
            except asyncio.CancelledError:
                logger.info("Scheduler stopped")
                break
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                await asyncio.sleep(60)
    
    async def send_morning_digest(self):
        """Утренняя подборка - до 10 новостей"""
        logger.info("Morning digest...")
        all_news = self.news_fetcher.get_all_news(max_per_source=3)
        
        unique = []
        for n in all_news:
            h = self._get_hash(n.title, n.link)
            if h not in self.sent_hashes:
                unique.append(n)
                self.sent_hashes.add(h)
        
        if not unique:
            logger.info("No new news for digest")
            return
        
        self._save_sent_hashes()
        selected = unique[:10]
        
        for n in selected:
            post = await self.publisher.prepare_post(n)
            if post:
                await self.bot._send_post(post)
            await asyncio.sleep(2)
        
        logger.info(f"Morning digest sent: {len(selected)} posts")
    
    async def run(self):
        """Главный цикл - запускаем и рассылку, и обработку команд"""
        if not self.bot.configure():
            logger.error("Cannot configure bot")
            return
        
        # Настраиваем обработчики команд
        self.bot.setup_handlers()
        
        # Запускаем параллельно
        await asyncio.gather(
            self.scheduler_loop(),
            self.bot.start_polling()
        )


async def main():
    bot = SimpleNewsBot()
    try:
        await bot.run()
    except KeyboardInterrupt:
        logger.info("Shutdown")
        await bot.bot.close()


if __name__ == '__main__':
    asyncio.run(main())
