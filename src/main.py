"""
Game News Bot - Morning News Digest

Bot for monitoring gaming news sites and sending daily digests to Telegram.
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import config
from scheduler import NewsScheduler

# Setup logging
def setup_logging():
    """Configure logging for the application"""
    log_format = "%(asctime)s | %(levelname)-8s | %(name)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Ensure log directory exists
    config.logging.log_dir.mkdir(parents=True, exist_ok=True)
    log_file = config.logging.log_dir / "bot.log"

    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, config.logging.level),
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, encoding="utf-8")
        ]
    )

    # Reduce noise from some libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("aiogram").setLevel(logging.INFO)
    logging.getLogger("apscheduler").setLevel(logging.INFO)


def print_banner():
    """Print application banner"""
    banner = """
╔══════════════════════════════════════════════════════════╗
║         🎮 GAME NEWS BOT - Утренняя подборка              ║
║                                                          ║
║  Мониторинг игровых новостей и доставка в Telegram       ║
╚══════════════════════════════════════════════════════════╝
    """
    print(banner)


def print_status(scheduler: NewsScheduler):
    """Print current status"""
    status = scheduler.get_status()

    print("\n📊 Статус:")
    print(f"   • Планировщик: {'▶️ Запущен' if status['running'] else '⏹ Остановлен'}")
    print(f"   • Telegram: {'✅ Настроен' if status['telegram_configured'] else '❌ Не настроен'}")
    print(f"   • Следующая отправка: {scheduler.get_next_run()}")
    print(f"   • Источников новостей: {len(config.sources.sources)}")
    print(f"   • Время отправки: {config.scheduler.morning_hour:02d}:{config.scheduler.morning_minute:02d} ({config.scheduler.timezone})")
    print("\n📰 Источники новостей:")

    for source in config.sources.sources:
        status_icon = "✅" if source.get("enabled", True) else "❌"
        print(f"   {status_icon} {source['name']} ({source['category']})")

    print("\n💡 Команды:")
    print("   Ctrl+C - Остановить бота")
    print("   Запуск news теперь: python -m src.main --send-now")
    print()


async def main():
    """Main application entry point with scheduler and polling"""
    setup_logging()
    logger = logging.getLogger(__name__)

    print_banner()

    # Create scheduler
    scheduler = NewsScheduler()

    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()
    shutdown_event = asyncio.Event()

    def signal_handler():
        logger.info("Received shutdown signal...")
        shutdown_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    try:
        # Start scheduler
        if not scheduler.start():
            print("❌ Не удалось запустить планировщик. Проверьте конфигурацию.")
            return 1

        # Setup command handlers
        scheduler.telegram_bot.setup_handlers(scheduler)

        print_status(scheduler)
        print("📱 Команды бота: /start /status /send /sources /schedule /test")
        print()

        # Start polling in background with auto-reconnect
        polling_task = asyncio.create_task(run_polling_with_reconnect(scheduler))

        # Keep running until shutdown
        async def wait_shutdown():
            await shutdown_event.wait()
            polling_task.cancel()
            try:
                await polling_task
            except asyncio.CancelledError:
                pass
        
        await wait_shutdown()

    except Exception as e:
        logger.error(f"Application error: {e}", exc_info=True)
        return 1
    finally:
        scheduler.stop()
        await scheduler.telegram_bot.close()
        logger.info("Bot stopped")

    return 0


async def run_polling_with_reconnect(scheduler):
    """Polling with automatic reconnection"""
    log = logging.getLogger(__name__)
    retry_delay = 5
    max_retries = 1000
    retries = 0
    
    while retries < max_retries:
        try:
            await scheduler.telegram_bot.dp.start_polling(scheduler.telegram_bot.bot)
            break  # Normal exit
        except asyncio.CancelledError:
            break
        except Exception as e:
            retries += 1
            log.warning(f"Polling error (retry {retries}): {e}")
            await asyncio.sleep(retry_delay)


async def send_now():
    """Send news immediately (for testing)"""
    setup_logging()
    logger = logging.getLogger(__name__)

    print_banner()
    print("📤 Отправка новостей...\n")

    scheduler = NewsScheduler()

    if not scheduler.telegram_bot.configure():
        print("❌ Не удалось настроить Telegram бота.")
        print("   Проверьте TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID в .env")
        return 1

    try:
        success = await scheduler.fetch_and_send_news()
        if success:
            print("\n✅ Рассылка выполнена успешно!")
        else:
            print("\n❌ Ошибка при отправке рассылки")
        return 0 if success else 1
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return 1
    finally:
        await scheduler.telegram_bot.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Game News Bot")
    parser.add_argument(
        "--send-now",
        action="store_true",
        help="Send news immediately instead of waiting for scheduled time"
    )

    args = parser.parse_args()

    if args.send_now:
        exit_code = asyncio.run(send_now())
    else:
        exit_code = asyncio.run(main())

    sys.exit(exit_code)
