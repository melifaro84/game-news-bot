"""
Scheduler module - handles automated news fetching and sending
Supports frequent posting schedule with deduplication
"""
import logging
import random
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
import hashlib

from config import config
from news_fetcher import NewsFetcher
from telegram_bot import TelegramNewsBot

logger = logging.getLogger(__name__)


class NewsScheduler:
    """Scheduler for automated news posting throughout the day"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=config.scheduler.timezone)
        self.news_fetcher = NewsFetcher(lookback_hours=24)  # 24h lookback for deduplication
        self.telegram_bot = TelegramNewsBot(ai_api_key=config.telegram.deepseek_api_key)
        self._sent_hashes = set()  # Track sent news by content hash
        self._setup_event_listeners()
        self._load_seen_hashes()

    def _setup_event_listeners(self):
        """Setup scheduler event listeners for logging"""
        self.scheduler.add_listener(
            self._on_job_executed,
            EVENT_JOB_EXECUTED | EVENT_JOB_ERROR
        )

    def _on_job_executed(self, event):
        """Log job execution events"""
        if event.exception:
            logger.error(f"Job {event.job_id} failed: {event.exception}")
        else:
            logger.info(f"Job {event.job_id} completed successfully")

    def _get_content_hash(self, title: str, link: str) -> str:
        """Generate unique hash for news content to detect duplicates"""
        content = f"{title.lower().strip()}|{link.lower().strip()}"
        return hashlib.md5(content.encode()).hexdigest()

    def _load_seen_hashes(self):
        """Load previously seen hashes from file"""
        try:
            with open('.sent_hashes', 'r') as f:
                self._sent_hashes = set(line.strip() for line in f if line.strip())
            logger.info(f"Loaded {len(self._sent_hashes)} previously sent news")
        except FileNotFoundError:
            logger.info("No previous history found, starting fresh")

    def _save_seen_hashes(self):
        """Save seen hashes to file"""
        try:
            with open('.sent_hashes', 'w') as f:
                for h in self._sent_hashes:
                    f.write(h + '\n')
        except Exception as e:
            logger.error(f"Failed to save hashes: {e}")

    def _filter_duplicates(self, news: list) -> list:
        """Filter out already sent news"""
        unique_news = []
        new_hashes = []

        for item in news:
            h = self._get_content_hash(item.title, item.link)
            if h not in self._sent_hashes and h not in new_hashes:
                unique_news.append(item)
                new_hashes.append(h)

        if new_hashes:
            self._sent_hashes.update(new_hashes)
            self._save_seen_hashes()

        return unique_news

    async def fetch_and_send_news(self):
        """Job: Fetch news and send to Telegram (2 random news)"""
        logger.info("Starting news fetch...")

        # Fetch all news
        all_news = self.news_fetcher.get_all_news(max_per_source=10)
        logger.info(f"Fetched {len(all_news)} news items")

        # Filter duplicates
        unique_news = self._filter_duplicates(all_news)
        logger.info(f"After deduplication: {len(unique_news)} unique news")

        if not unique_news:
            logger.info("No new news to send")
            return

        # Select 2 random news from different sources
        random.shuffle(unique_news)

        # Try to get 2 news from different sources
        selected = []
        used_sources = set()

        for item in unique_news:
            if item.source not in used_sources and len(selected) < 2:
                selected.append(item)
                used_sources.add(item.source)

        # If we don't have 2 different sources, just take 2 random
        if len(selected) < 2:
            selected = unique_news[:2]

        if selected:
            sent_count = await self.telegram_bot.send_news_posts(selected)
            logger.info(f"Sent {sent_count} news posts")

    async def fetch_and_send_morning_digest(self):
        """Job: Morning digest with more news (all unique)"""
        logger.info("Starting morning digest...")

        all_news = self.news_fetcher.get_all_news(max_per_source=5)
        unique_news = self._filter_duplicates(all_news)

        if unique_news:
            # Limit morning digest to avoid spam
            digest_news = unique_news[:10]
            sent_count = await self.telegram_bot.send_news_posts(digest_news)
            logger.info(f"Sent morning digest: {sent_count} posts")

    def start(self):
        """Start the scheduler with frequent posting schedule"""
        if not self.telegram_bot.configure():
            logger.error("Cannot start scheduler: Telegram bot not configured")
            return False

        # Morning digest at 7:00 (more news)
        self.scheduler.add_job(
            self.fetch_and_send_morning_digest,
            CronTrigger(hour=7, minute=0, timezone=config.scheduler.timezone),
            id="morning_digest",
            name="Утренняя подборка",
            replace_existing=True
        )

        # Frequent posting: every 1.5 hours from 8:30 to 22:30 (about 10 times)
        posting_hours = [8, 10, 11, 13, 14, 16, 17, 19, 20, 22]

        for hour in posting_hours:
            self.scheduler.add_job(
                self.fetch_and_send_news,
                CronTrigger(hour=hour, minute=30, timezone=config.scheduler.timezone),
                id=f"midday_{hour}",
                name=f"Обновление {hour}:30",
                replace_existing=True
            )

        self.scheduler.start()
        schedule = "07:00, 8:30, 10:30, 11:30, 13:30, 14:30, 16:30, 17:30, 19:30, 20:30, 22:30"
        logger.info(f"Scheduler started. Posting schedule (МСК): {schedule}")

        return True

    def stop(self):
        """Stop the scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("Scheduler stopped")

    def get_next_run(self) -> str:
        """Get next scheduled run time"""
        jobs = self.scheduler.get_jobs()
        if jobs:
            next_job = min(jobs, key=lambda j: j.next_run_time if j.next_run_time else datetime.max)
            if next_job.next_run_time:
                return next_job.next_run_time.strftime("%d.%m.%Y %H:%M:%S")
        return "Не запланировано"

    def get_status(self) -> dict:
        """Get scheduler status"""
        return {
            "running": self.scheduler.running,
            "jobs": [
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run": job.next_run_time.strftime("%d.%m.%Y %H:%M") if job.next_run_time else "N/A"
                }
                for job in self.scheduler.get_jobs()
            ],
            "telegram_configured": config.telegram.is_configured(),
            "seen_news_count": len(self._sent_hashes)
        }
