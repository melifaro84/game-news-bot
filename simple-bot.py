#!/usr/bin/env python3
"""
Simple News Bot - без APScheduler, просто бесконечный цикл
Запускается и работает пока не упадёт
"""
import asyncio
import logging
import sys
from datetime import datetime, timedelta
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
    
    async def send_news(self):
        """Отправить 2 новости"""
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
            return
        
        # Берём 2 из разных источников
        import random
        random.shuffle(unique)
        
        selected = []
        used_sources = set()
        for n in unique:
            if n.source not in used_sources and len(selected) < 2:
                selected.append(n)
                used_sources.add(n.source)
        
        if len(selected) < 2:
            selected = unique[:2]
        
        self._save_sent_hashes()
        
        # Отправляем
        for n in selected:
            logger.info(f"Sending: {n.title[:50]}...")
            post = await self.publisher.prepare_post(n)
            if post:
                await self.bot._send_post(post)
                await asyncio.sleep(2)
        
        logger.info(f"Sent {len(selected)} posts")
    
    def should_send(self):
        """Проверяем, пора ли отправлять"""
        now = datetime.now()
        hour = now.hour
        minute = now.minute
        
        # Расписание: 07:00, 8:30, 10:30, 11:30, 13:30, 14:30, 16:30, 17:30, 19:30, 20:30, 22:30
        schedule = [(7, 0), (8, 30), (10, 30), (11, 30), (13, 30), (14, 30), 
                   (16, 30), (17, 30), (19, 30), (20, 30), (22, 30)]
        
        for h, m in schedule:
            if h == hour and 0 <= minute < 30:
                return True
        return False
    
    async def run(self):
        """Главный цикл"""
        if not self.bot.configure():
            logger.error("Cannot configure bot")
            return
        
        logger.info("Bot started!")
        last_send_hour = -1
        
        while True:
            try:
                now = datetime.now()
                
                # Проверяем каждый час
                if now.minute >= 0 and now.minute < 30:
                    if self.should_send() and now.hour != last_send_hour:
                        last_send_hour = now.hour
                        await self.send_news()
                
                await asyncio.sleep(60)  # Проверяем каждую минуту
                
            except asyncio.CancelledError:
                logger.info("Bot stopped")
                break
            except Exception as e:
                logger.error(f"Error: {e}")
                await asyncio.sleep(10)


async def main():
    bot = SimpleNewsBot()
    try:
        await bot.run()
    except KeyboardInterrupt:
        logger.info("Shutdown")


if __name__ == '__main__':
    asyncio.run(main())
