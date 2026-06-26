#!/usr/bin/env python3
"""
Railway-ready News Bot
- Просыпается по HTTP запросу от cron
- Отправляет новости
- Засыпает обратно
"""
import os
import sys
import asyncio
import logging
import hashlib
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from config import config
from news_fetcher import NewsFetcher
from telegram_bot import TelegramNewsBot
from post_publisher import PostPublisher

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)


class RailwayNewsBot:
    def __init__(self):
        self.bot = TelegramNewsBot(config.telegram.deepseek_api_key)
        self.sent_hashes = self._load_hashes()
        
    def _load_hashes(self):
        try:
            with open('.sent_hashes', 'r') as f:
                return set(line.strip() for line in f if line.strip())
        except:
            return set()
    
    def _save_hashes(self):
        with open('.sent_hashes', 'w') as f:
            for h in self.sent_hashes:
                f.write(h + '\n')
    
    def _hash(self, title, link):
        return hashlib.md5(f"{title.lower()}|{link.lower()}".encode()).hexdigest()
    
    async def send_news(self, count=2):
        """Отправить N новостей"""
        logger.info("Starting news fetch...")
        
        fetcher = NewsFetcher(lookback_hours=24)
        all_news = fetcher.get_all_news(max_per_source=5)
        
        # Дедупликация
        unique = []
        for n in all_news:
            h = self._hash(n.title, n.link)
            if h not in self.sent_hashes:
                unique.append(n)
                self.sent_hashes.add(h)
        
        if not unique:
            logger.info("No new news")
            return 0
        
        self._save_hashes()
        
        # Берём из разных источников
        import random
        random.shuffle(unique)
        
        selected = []
        used = set()
        for n in unique:
            if n.source not in used and len(selected) < count:
                selected.append(n)
                used.add(n.source)
        
        if len(selected) < count:
            selected = unique[:count]
        
        # Отправка
        if not self.bot.configure():
            logger.error("Cannot configure bot")
            return 0
        
        publisher = PostPublisher(config.telegram.deepseek_api_key)
        sent = 0
        
        for n in selected:
            logger.info(f"Sending: {n.title[:50]}...")
            post = await publisher.prepare_post(n)
            if post:
                success = await self.bot._send_post(post)
                if success:
                    sent += 1
            await asyncio.sleep(2)
        
        logger.info(f"Sent {sent} posts")
        return sent
    
    async def send_morning_digest(self):
        """Утренняя подборка - до 10 новостей"""
        logger.info("Starting morning digest...")
        
        fetcher = NewsFetcher(lookback_hours=24)
        all_news = fetcher.get_all_news(max_per_source=3)
        
        unique = []
        for n in all_news:
            h = self._hash(n.title, n.link)
            if h not in self.sent_hashes:
                unique.append(n)
                self.sent_hashes.add(h)
        
        if not unique:
            logger.info("No new news for digest")
            return 0
        
        self._save_hashes()
        
        # До 10 новостей
        selected = unique[:10]
        
        if not self.bot.configure():
            return 0
        
        publisher = PostPublisher(config.telegram.deepseek_api_key)
        sent = 0
        
        for n in selected:
            post = await publisher.prepare_post(n)
            if post:
                success = await self.bot._send_post(post)
                if success:
                    sent += 1
            await asyncio.sleep(2)
        
        logger.info(f"Morning digest sent: {sent} posts")
        return sent


async def main():
    """Главная функция"""
    bot = RailwayNewsBot()
    
    # Определяем тип отправки
    mode = os.environ.get('SEND_MODE', 'normal')
    
    logger.info(f"Bot started (mode: {mode})")
    
    if mode == 'morning':
        await bot.send_morning_digest()
    else:
        await bot.send_news(count=2)
    
    logger.info("Bot finished, going to sleep...")
    await bot.bot.close()


if __name__ == '__main__':
    asyncio.run(main())
