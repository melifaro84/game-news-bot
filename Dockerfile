FROM python:3.11-slim

WORKDIR /app

# Устанавливаем зависимости
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Копируем код
COPY . .

# Устанавливаем Python пакеты
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir openai deep-translator aiohttp-socks

# Создаём файл для хешей
RUN touch .sent_hashes

# Запускаем бота
CMD ["python", "simple-bot.py"]
