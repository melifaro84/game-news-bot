# 🚂 Деплой Game News Bot на Railway

## Быстрый старт

### 1. Подготовка

```bash
# Установите Railway CLI
curl -fsSL https://railway.app/install.sh | sh

# Или используйте GitHub Actions
```

### 2. Деплой через GitHub

1. Загрузите код на GitHub:
```bash
cd game-news-bot
git init
git add .
git commit -m "Game News Bot"
git remote add origin https://github.com/YOUR_USERNAME/game-news-bot.git
git push -u origin main
```

2. Подключите репозиторий в Railway:
   - Зайдите на https://railway.app
   - New Project → Deploy from GitHub
   - Выберите репозиторий

3. Добавьте переменные окружения в Railway Dashboard:
   - `TELEGRAM_BOT_TOKEN` - токен бота
   - `TELEGRAM_CHAT_ID` - ID канала
   - `DEEPSEEK_API_KEY` - ключ API DeepSeek

### 3. Настройка Cron (EasyCron)

1. Зарегистрируйтесь на https://easycron.com (бесплатно)

2. Добавьте задачи для каждого времени:

```
URL: https://your-railway-app.railway.app/send
Метод: POST
```

**Расписание (cron format):**

| Время | Cron |
|-------|------|
| 07:00 МСК | `0 4 * * *` (утренняя) |
| 08:30 МСК | `30 5 * * *` |
| 10:30 МСК | `30 7 * * *` |
| 11:30 МСК | `30 8 * * *` |
| 13:30 МСК | `30 10 * * *` |
| 14:30 МСК | `30 11 * * *` |
| 16:30 МСК | `30 13 * * *` |
| 17:30 МСК | `30 14 * * *` |
| 19:30 МСК | `30 16 * * *` |
| 20:30 МСК | `30 17 * * *` |
| 22:30 МСК | `30 19 * * *` |

Для утренней подборки добавьте переменную:
- **Body/POST Data:** `mode=morning`

### 4. Добавьте HTTP endpoint

Добавьте в `railway-send.py`:

```python
from aiohttp import web

async def send_handler(request):
    """HTTP endpoint для cron"""
    mode = request.query.get('mode', 'normal')
    
    bot = RailwayNewsBot()
    if mode == 'morning':
        await bot.send_morning_digest()
    else:
        await bot.send_news(count=2)
    
    return web.Response(text="OK")

app = web.Application()
app.router.add_post('/send', send_handler)

if __name__ == '__main__':
    web.run_app(app, port=8080)
```

---

## Альтернатива: VPS

Если Railway не подходит, возьмите VPS:
- Timeweb Cloud (~150₽/мес)
- Selectel (~200₽/мес)

SSH, установите Python и запустите `simple-bot.py`
