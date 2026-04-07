FROM python:3.11-slim

# Системные зависимости для Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget gnupg \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 libgbm1 \
    libpango-1.0-0 libcairo2 libasound2 libxshmfence1 \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Установка Google Chrome (исправленный способ без apt-key)
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor > /etc/apt/trusted.gpg.d/google-chrome.gpg \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Указываем тот же путь для браузеров, который использует Render (кэш)
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/rendercache
RUN playwright install

COPY . .

# Запуск с портом из переменной окружения Render
CMD uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}