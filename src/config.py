"""
Configuration for Game News Bot
"""
import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)


@dataclass
class TelegramConfig:
    bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")

    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)


@dataclass
class SchedulerConfig:
    morning_hour: int = int(os.getenv("MORNING_HOUR", "7"))
    morning_minute: int = int(os.getenv("MORNING_MINUTE", "0"))
    timezone: str = os.getenv("TIMEZONE", "Europe/Moscow")


@dataclass
class LoggingConfig:
    level: str = os.getenv("LOG_LEVEL", "INFO")
    log_dir: Path = Path(__file__).parent.parent / "logs"


@dataclass
class GameSourcesConfig:
    """Game news sources with RSS feeds"""
    sources: list = None

    def __post_init__(self):
        if self.sources is None:
            self.sources = [
                {
                    "name": "RetroDrom",
                    "url": "https://retrodrom.games/",
                    "category": "Ретро-игры",
                    "enabled": True,
                    "type": "web"
                },
                {
                    "name": "RetroDodo",
                    "url": "https://retrododo.com/feed/",
                    "category": "Ретро-игры",
                    "enabled": True,
                    "type": "rss"
                },
                {
                    "name": "RetroNews",
                    "url": "https://www.retronews.com/feed/",
                    "category": "Ретро-игры",
                    "enabled": True,
                    "type": "rss"
                },
                {
                    "name": "GameSpot",
                    "url": "https://www.gamespot.com/feeds/mashup/",
                    "category": "Игровые новости",
                    "enabled": True,
                    "type": "rss"
                },
                {
                    "name": "GoNintendo",
                    "url": "https://gonintendo.com/rss.xml",
                    "category": "Nintendo",
                    "enabled": True,
                    "type": "rss"
                },
                {
                    "name": "Nintendo Insider",
                    "url": "https://www.nintendo-insider.com/feed",
                    "category": "Nintendo",
                    "enabled": True,
                    "type": "rss"
                },
                {
                    "name": "ixbt.games",
                    "url": "https://ixbt.games/news",
                    "category": "Портативные консоли",
                    "enabled": True,
                    "type": "web",
                    "keywords": ["portable", "handheld", "switch", "steam deck", "rog ally", "ayaneo", "pocket", "legion go", "портативн", "handheld", "Nintendo Switch", "Switch 2", "PS Portal", "мобильн", "карман"]
                },
            ]


@dataclass
class AppConfig:
    telegram: TelegramConfig = None
    scheduler: SchedulerConfig = None
    logging: LoggingConfig = None
    sources: GameSourcesConfig = None

    def __post_init__(self):
        self.telegram = TelegramConfig()
        self.scheduler = SchedulerConfig()
        self.logging = LoggingConfig()
        self.sources = GameSourcesConfig()


# Global config instance
config = AppConfig()
