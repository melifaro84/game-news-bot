# 🎮 Game News Bot

Telegram-бот для мониторинга игровых новостей и утренних рассылок.

## Возможности

- 📰 Мониторинг RSS-лент популярных игровых сайтов
- 🌅 Автоматическая утренняя рассылка подборки новостей
- 📊 Группировка новостей по категориям
- ⚙️ Гибкая настройка источников и расписания

## Установка

### 1. Клонирование и зависимости

```bash
cd /home/user/game-news-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Настройка

Скопируйте пример конфигурации:

```bash
cp .env.example .env
```

Отредактируйте `.env`:

```env
# Telegram Bot Token от @BotFather
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz

# Ваш Telegram Chat ID (получите через @userinfobot)
TELEGRAM_CHAT_ID=123456789

# Время отправки (по умолчанию 7:00)
MORNING_HOUR=7
MORNING_MINUTE=0

# Часовой пояс
TIMEZONE=Europe/Moscow
```

### 3. Запуск

**Обычный запуск (планировщик):**
```bash
source venv/bin/activate
python -m src.main
```

**Отправка новостей сейчас (тест):**
```bash
source venv/bin/activate
python -m src.main --send-now
```

## Настройка источников новостей

Источники настраиваются в файле `src/config.py`:

```python
sources: list = [
    {
        "name": "StopGame.ru",
        "url": "https://stopgame.ru/rss",
        "category": "Игровые новости",
        "enabled": True
    },
    # Добавьте свои источники...
]
```

## Структура проекта

```
game-news-bot/
├── .env.example          # Пример конфигурации
├── requirements.txt       # Python зависимости
├── README.md             # Документация
├── src/
│   ├── __init__.py
│   ├── config.py         # Конфигурация
│   ├── news_fetcher.py   # Парсинг RSS
│   ├── telegram_bot.py   # Telegram бот
│   ├── scheduler.py      # Планировщик
│   └── main.py           # Точка входа
└── logs/                 # Логи бота
```

## Получение Telegram токена

1. Откройте [@BotFather](https://t.me/BotFather) в Telegram
2. Отправьте `/newbot`
3. Следуйте инструкциям и сохраните токен

## Получение Chat ID

1. Откройте [@userinfobot](https://t.me/userinfobot) в Telegram
2. Отправьте `/start`
3. Скопируйте ваш числовой ID

## Crontab для автозапуска

Добавьте в crontab для автозапуска при перезагрузке сервера:

```bash
crontab -e
```

Добавьте строку:

```
@reboot cd /home/user/game-news-bot && source venv/bin/activate && python -m src.main >> /home/user/game-news-bot/logs/cron.log 2>&1
```

## Мониторинг

Логи бота сохраняются в:
- `logs/bot.log` — основной лог
- Вывод в stdout

Проверка лога:
```bash
tail -f logs/bot.log
```

## Безопасность

- Никогда не коммитьте `.env` файл в git
- Держите токены в безопасности
- Используйте разные токены для dev/prod
