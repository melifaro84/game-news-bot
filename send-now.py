#!/usr/bin/env python3
"""
Ручная отправка новостей - запустить вручную из консоли
"""
import asyncio
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from config import config
from news_fetcher import NewsFetcher
from telegram_bot import TelegramNewsBot
from post_publisher import PostPublisher
import hashlib

async def send_news(count=2):
    """Отправить N новостей"""
    print(f"Fetching news...")
    
    fetcher = NewsFetcher(lookback_hours=24)
    all_news = fetcher.get_all_news(max_per_source=5)
    
    # Загружаем уже отправленные
    sent_hashes = set()
    try:
        with open('.sent_hashes', 'r') as f:
            sent_hashes = set(line.strip() for line in f if line.strip())
    except:
        pass
    
    # Фильтр дубликатов
    unique = []
    for n in all_news:
        h = hashlib.md5(f"{n.title.lower()}|{n.link.lower()}".encode()).hexdigest()
        if h not in sent_hashes:
            unique.append(n)
            sent_hashes.add(h)
    
    if not unique:
        print("No new news found!")
        return
    
    # Выбираем из разных источников
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
    
    # Сохраняем хеши
    with open('.sent_hashes', 'w') as f:
        for h in sent_hashes:
            f.write(h + '\n')
    
    # Инициализируем бота
    bot = TelegramNewsBot(config.telegram.deepseek_api_key)
    if not bot.configure():
        print("Failed to configure bot")
        return
    
    publisher = PostPublisher(config.telegram.deepseek_api_key)
    
    print(f"Sending {len(selected)} news...")
    
    for n in selected:
        print(f"  - {n.title[:60]}...")
        post = await publisher.prepare_post(n)
        if post:
            await bot._send_post(post)
        await asyncio.sleep(2)
    
    print(f"Done! Sent {len(selected)} posts.")
    await bot.close()


if __name__ == '__main__':
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    asyncio.run(send_news(count))
