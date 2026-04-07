FROM python:3.11-slim

# Системные зависимости для Playwright (Chromium + Headless Shell)
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget gnupg \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 libgbm1 \
    libpango-1.0-0 libcairo2 libasound2 libxshmfence1 \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем Google Chrome (если нужен для undetected-chromedriver – для Ozon)
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Ключевой момент: указываем тот же путь, который использует Render для кэша браузеров
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/rendercache

# Устанавливаем ВСЕ браузеры Playwright (Chromium + Headless Shell)
RUN playwright install

COPY . .

# Не нужны ни Xvfb, ни DISPLAY – Playwright работает headless
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]