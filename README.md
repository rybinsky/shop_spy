# 🔍 ShopSpy — AI-помощник для умных покупок

**ShopSpy** — браузерное расширение с бэкендом для отслеживания цен на Wildberries и Ozon. Помогает экономить, обнаруживать фейковые скидки и получать уведомления о снижении цен в Telegram.

---

## 📋 Возможности

| Функция | Описание |
|---------|----------|
| 📊 **История цен** | Автоматический сбор цен при просмотре товаров |
| 🚨 **Детектор фейковых скидок** | Анализ реальности скидки на основе истории |
| 🤖 **AI-анализ отзывов** | Краткая выжимка плюсов и минусов товара |
| 📱 **Telegram-уведомления** | Оповещения о снижении цен |
| 🎯 **Целевые цены** | Уведомление когда цена достигнет желаемого уровня |
| 🔄 **Сравнение площадок** | Быстрый поиск товара на другом маркетплейсе |

---

## 🚀 Быстрый старт

### 1. Установка

```bash
git clone https://github.com/your-repo/shopspy.git
cd shopspy
pip install -r requirements.txt
```

### 2. Создание Telegram-бота

1. Откройте [@BotFather](https://t.me/BotFather) в Telegram
2. Отправьте `/newbot` и следуйте инструкциям
3. **Скопируйте токен** — он понадобится для запуска

### 3. Получение Chat ID

1. Откройте [@userinfobot](https://t.me/userinfobot) в Telegram
2. Отправьте `/start`
3. **Скопируйте ваш Chat ID**

### 4. Запуск сервера

```bash
# macOS / Linux
TELEGRAM_BOT_TOKEN=ваш_токен python -m backend.main

# Windows (PowerShell)
$env:TELEGRAM_BOT_TOKEN="ваш_токен"
python -m backend.main
```

Сервер запустится на http://localhost:8000

### 5. Установка расширения

1. Откройте `chrome://extensions/`
2. Включите **Режим разработчика**
3. Нажмите **Загрузить распакованное расширение**
4. Выберите папку `extension/`

### 6. Привязка Telegram

1. Откройте http://localhost:8000
2. Введите ваш Chat ID в разделе "Telegram уведомления"
3. Нажмите "Привязать"

---

## ⚙️ Конфигурация

### Переменные окружения

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `TELEGRAM_BOT_TOKEN` | Токен Telegram бота | — |
| `GEMINI_API_KEY` | API ключ Google Gemini (бесплатно) | — |
| `ANTHROPIC_API_KEY` | API ключ Claude (платно) | — |
| `CRAWL_INTERVAL` | Интервал проверки цен (сек) | `21600` (6 ч) |
| `RATE_LIMIT_PER_IP` | Лимит AI-запросов в день на IP | `10` |
| `RATE_LIMIT_GLOBAL` | Глобальный лимит AI-запросов | `200` |
| `ENVIRONMENT` | Окружение: `development` / `production` | `development` |
| `PORT` | Порт сервера | `8000` |

### AI-анализ отзывов

**Google Gemini (бесплатно):**
1. Перейдите на [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Создайте API ключ
3. Установите: `GEMINI_API_KEY=ваш_ключ`

**Anthropic Claude (платно):**
1. Получите ключ на [Anthropic Console](https://console.anthropic.com/)
2. Установите: `ANTHROPIC_API_KEY=ваш_ключ`

---

## 📖 Руководство пользователя

### Панель расширения

При открытии товара на WB или Ozon появляется панель ShopSpy:

```
┌─────────────────────────────────┐
│ 🔍 ShopSpy                   [−]│
├─────────────────────────────────┤
│ 💰 Текущая цена                 │
│    1 299 ₽  1 599 ₽  −19%      │
│                                 │
│ 📊 Анализ цены                  │
│    ✅ Хорошая цена!             │
│                                 │
│ 📈 История цен                  │
│    [график]                     │
│                                 │
│ [🔔 Отслеживать]                │
│ [🤖 Анализировать отзывы]       │
└─────────────────────────────────┘
```

### Вердикты по цене

| Иконка | Статус | Описание |
|--------|--------|----------|
| ✅ | Хорошая цена | Цена ниже средней или равна минимуму |
| ⚠️ | Дорого | Цена выше средней |
| 🚨 | Фейковая скидка | Цена была завышена перед "скидкой" |
| ℹ️ | Обычная цена | Цена в пределах нормы |

### Команды Telegram-бота

| Команда | Описание |
|---------|----------|
| `/start` | Показать Chat ID |
| `/list` | Отслеживаемые товары |
| `/stop` | Отключить уведомления |
| `/help` | Справка |

---

## 🛠️ Руководство разработчика

### Структура проекта

```
shopspy/
├── backend/
│   ├── __init__.py
│   ├── main.py              # Точка входа FastAPI
│   ├── config.py            # Конфигурация (dataclasses)
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py        # API endpoints
│   ├── db/
│   │   ├── __init__.py
│   │   ├── database.py      # SQLite connection manager
│   │   └── repositories/
│   │       ├── prices.py    # Репозиторий цен
│   │       ├── alerts.py    # Репозиторий уведомлений
│   │       └── users.py     # Репозиторий пользователей
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py       # Pydantic модели
│   ├── services/
│   │   ├── __init__.py
│   │   ├── crawler.py       # Фоновый сборщик цен
│   │   ├── price_analyzer.py # Анализ цен
│   │   └── ai_analyzer.py   # AI-анализ отзывов
│   ├── telegram_bot/
│   │   ├── __init__.py
│   │   └── bot.py           # Telegram бот
│   └── utils/
│       ├── __init__.py
│       ├── logging.py       # Настройка логирования
│       └── marketplace_api.py # API маркетплейсов
├── extension/
│   ├── manifest.json
│   ├── content/
│   │   ├── shared.js        # Общий код расширения
│   │   ├── wb.js            # Wildberries
│   │   ├── ozon.js          # Ozon
│   │   └── shopspy.css
│   └── popup/
│       └── popup.html
├── templates/
│   └── dashboard.html
├── data/                     # SQLite база
├── requirements.txt
└── README.md
```

### Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                        FastAPI App                           │
│  main.py → lifespan → init_database → start_crawler         │
│                         → start_telegram_bot                 │
├─────────────────────────────────────────────────────────────┤
│  API Layer (api/routes.py)                                   │
│  ├── /api/price        → PricesRepository                    │
│  ├── /api/reviews      → AIAnalyzer                          │
│  ├── /api/telegram     → UsersRepository                     │
│  └── /api/alerts       → AlertsRepository                    │
├─────────────────────────────────────────────────────────────┤
│  Services                                                    │
│  ├── CrawlerService    → периодическая проверка цен          │
│  ├── PriceAnalyzer     → анализ истории цен                  │
│  └── AIAnalyzer        → Gemini/Claude API                   │
├─────────────────────────────────────────────────────────────┤
│  Data Layer                                                  │
│  ├── Database          → SQLite connection manager           │
│  └── Repositories      → prices, alerts, users               │
├─────────────────────────────────────────────────────────────┤
│  External                                                    │
│  ├── TelegramBot       → aiogram 3.x                        │
│  └── MarketplaceAPI    → httpx async client                  │
└─────────────────────────────────────────────────────────────┘
```

### Добавление нового маркетплейса

**1. Content script** `extension/content/ym.js`:

```javascript
(function() {
    'use strict';
    const PLATFORM = 'ym';

    function getProductId() {
        const m = window.location.pathname.match(/\/product\/(\d+)/);
        return m ? m[1] : null;
    }

    function getCurrentPrice() {
        const el = document.querySelector('[data-auto="price"]');
        return el ? parseFloat(el.textContent.replace(/[^\d]/g, '')) : null;
    }

    function getProductName() {
        const el = document.querySelector('h1');
        return el ? el.textContent.trim() : '';
    }

    async function init() {
        const productId = getProductId();
        if (!productId) return;

        SHOPSPY.createPanel();
        const price = getCurrentPrice();
        const name = getProductName();

        if (price) {
            await SHOPSPY.sendPrice(PLATFORM, productId, name, price);
        }

        const h = await SHOPSPY.getHistory(PLATFORM, productId);
        SHOPSPY.renderPanel({
            history: h.history,
            analysis: h.analysis,
            productName: name,
            price,
            platform: PLATFORM,
            productId
        });
    }

    setTimeout(init, 2000);
})();
```

**2. Добавить в** `extension/manifest.json`:

```json
{
    "content_scripts": [{
        "matches": ["https://market.yandex.ru/*"],
        "js": ["content/shared.js", "content/ym.js"],
        "css": ["content/shopspy.css"]
    }],
    "host_permissions": ["https://market.yandex.ru/*"]
}
```

**3. Добавить API** в `backend/utils/marketplace_api.py`:

```python
async def fetch_ym_price(self, client: httpx.AsyncClient, product_id: str) -> Optional[dict]:
    url = f"https://market.yandex.ru/api/product/{product_id}"
    # ... реализация
```

### Запуск в режиме разработки

```bash
# С отладочными логами
ENVIRONMENT=development python -m backend.main

# С автоперезагрузкой
uvicorn backend.main:app --reload --port 8000

# Тестовый обход цен
curl -X POST http://localhost:8000/api/crawl
```

---

## 🚢 Деплой на Render.com

### render.yaml

```yaml
services:
  - type: web
    name: shopspy
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: python -m backend.main
    envVars:
      - key: ENVIRONMENT
        value: production
      - key: TELEGRAM_BOT_TOKEN
        sync: false
      - key: GEMINI_API_KEY
        sync: false
      - key: PORT
        value: 8000
```

### Шаги

1. Создайте Web Service на Render
2. Подключите GitHub репозиторий
3. Добавьте переменные окружения:
   - `TELEGRAM_BOT_TOKEN`
   - `GEMINI_API_KEY`
   - `ENVIRONMENT=production`

4. Обновите `extension/content/shared.js`:

```javascript
const SHOPSPY = {
    API_BASE: 'https://your-app.onrender.com',
    // ...
};
```

5. Пересоберите расширение и установите заново

---

## 📊 API Reference

### Prices

```http
POST /api/price
Content-Type: application/json

{
    "platform": "wb",
    "product_id": "12345678",
    "product_name": "Товар",
    "price": 1499.0,
    "original_price": 1999.0,
    "url": "https://..."
}
```

```http
GET /api/price/history?platform=wb&product_id=12345678

Response: {
    "history": [...],
    "analysis": {
        "verdict": "good_deal",
        "message": "✅ Хорошая цена!",
        "min_price": 1299,
        "max_price": 1999,
        "avg_price": 1599
    }
}
```

### AI Analysis

```http
POST /api/reviews/analyze
Content-Type: application/json

{
    "platform": "wb",
    "product_id": "12345678",
    "product_name": "Товар",
    "reviews": ["Отличный товар!", "Рекомендую"]
}

Response: {
    "summary": {
        "pros": ["Качество", "Цена"],
        "cons": ["Доставка"],
        "rating_honest": 4.5,
        "buy_recommendation": "yes"
    }
}
```

### Alerts

```http
POST /api/alerts
Content-Type: application/json

{
    "chat_id": 123456789,
    "platform": "wb",
    "product_id": "12345678",
    "target_price": 1200.0,
    "url": "https://..."
}
```

---

## 🔒 Безопасность

- Все данные хранятся локально (SQLite)
- Нет регистрации — привязка через Telegram Chat ID
- Rate limiting для AI-запросов
- Открытый исходный код

---

## 📜 Лицензия

MIT License

---

## 🗺️ Roadmap

- [ ] Сравнение цен между WB, Ozon, Яндекс.Маркет
- [ ] Детектор накрученных отзывов
- [ ] Прогнозирование цен (ML)
- [ ] Мобильное приложение
- [ ] Облачная синхронизация

---

<p align="center">
  Сделано с ❤️ для умных покупателей
</p>