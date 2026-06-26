#!/usr/bin/env python3
"""
Simple News Bot - автоматическая рассылка новостей по расписанию
БЕЗ polling - просто работает по расписанию
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
        self.last_sent = {}  # Track last send time per slot
        
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
        """Главный цикл - только автоматическая рассылка"""
        if not self.bot.configure():
            logger.error("Cannot configure bot")
            return
        
        logger.info("=" * 50)
        logger.info("Bot started in AUTO mode!")
        logger.info("Schedule:")
        logger.info("  07:00 - Morning digest (10 news)")
        logger.info("  8:30, 10:30, 11:30, 13:30, 14:30")
        logger.info("  16:30, 17:30, 19:30, 20:30, 22:30")
        logger.info("=" * 50)
        
        while True:
            try:
                now = datetime.now()
                hour = now.hour
                minute = now.minute
                
                # Расписание
                schedule = {
                    (7, 0): ('morning', 10),    # Утро - 10 новостей
                    (8, 30): ('normal', 2),
                    (10, 30): ('normal', 2),
                    (11, 30): ('normal', 2),
                    (13, 30): ('normal', 2),
                    (14, 30): ('normal', 2),
                    (16, 30): ('normal', 2),
                    (17, 30): ('normal', 2),
                    (19, 30): ('normal', 2),
                    (20, 30): ('normal', 2),
                    (22, 30): ('normal', 2),
                }
                
                # Проверяем расписание
                for (h, m), (mode, count) in schedule.items():
                    if h == hour and abs(minute - m) < 3:  # ±3 минуты
                        send_key = (h, m)
                        if send_key not in self.last_sent:
                            self.last_sent[send_key] = None
                        
                        # Не отправляем дважды
                        import time
                        if self.last_sent[send_key] is None or \
                           (time.time() - self.last_sent[send_key]) > 3600:
                            
                            self.last_sent[send_key] = time.time()
                            
                            logger.info(f"Scheduled send: {h}:{m} ({mode}, {count} news)")
                            
                            if mode == 'morning':
                                await self.send_morning_digest()
                            else:
                                await self.send_news(count)
                        break
                
                await asyncio.sleep(60)  # Проверяем каждую минуту
                
            except asyncio.CancelledError:
                logger.info("Bot stopped")
                break
            except Exception as e:
                logger.error(f"Error: {e}")
                await asyncio.sleep(60)


async def main():
    bot = SimpleNewsBot()
    try:
        await bot.run()
    except KeyboardInterrupt:
        logger.info("Shutdown")


if __name__ == '__main__':
    asyncio.run(main())
