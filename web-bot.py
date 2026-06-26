#!/usr/bin/env python3
"""
Web Bot - просыпается по HTTP запросу, отправляет новости, засыпает
Идеально для Goorm / serverless
"""
import os
import sys
import asyncio
import logging
import hashlib
from datetime import datetime
from pathlib import Path

from aiohttp import web

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from config import config
from news_fetcher import NewsFetcher
from telegram_bot import TelegramNewsBot
from post_publisher import PostPublisher

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)


class WebNewsBot:
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
        logger.info("Fetching news...")
        
        fetcher = NewsFetcher(lookback_hours=24)
        all_news = fetcher.get_all_news(max_per_source=5)
        
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
        """Утренняя подборка"""
        logger.info("Morning digest...")
        
        fetcher = NewsFetcher(lookback_hours=24)
        all_news = fetcher.get_all_news(max_per_source=3)
        
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
        
        logger.info(f"Morning digest: {sent} posts")
        return sent


async def handle_send(request):
    """Главный обработчик - вызывается по HTTP"""
    mode = request.query.get('mode', 'normal')
    
    try:
        bot = WebNewsBot()
        
        if mode == 'morning':
            count = await bot.send_morning_digest()
        else:
            count = await bot.send_news(count=2)
        
        return web.json_response({
            'status': 'ok',
            'sent': count,
            'time': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error: {e}")
        return web.json_response({
            'status': 'error',
            'error': str(e)
        }, status=500)
    finally:
        await bot.bot.close()


async def handle_health(request):
    """Health check"""
    return web.json_response({'status': 'ok'})


def create_app():
    """Создать приложение"""
    app = web.Application()
    app.router.add_get('/health', handle_health)
    app.router.add_post('/send', handle_send)
    app.router.add_get('/send', handle_send)
    return app


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    logger.info(f"Starting web bot on port {port}...")
    web.run_app(create_app(), host='0.0.0.0', port=port)
