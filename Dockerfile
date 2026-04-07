FROM python:3.11-slim

# System deps for Playwright (WB) + Chrome/Xvfb (Ozon)
RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
    wget gnupg \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 libgbm1 \
    libpango-1.0-0 libcairo2 libasound2 libxshmfence1 \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Install Chrome for undetected-chromedriver (Ozon)
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install chromium

COPY . .

ENV DISPLAY=:99
ENV RENDER=1

# Start Xvfb + app
CMD Xvfb :99 -screen 0 1280x720x24 -nolisten tcp & \
    sleep 1 && \
    python -m backend.main
