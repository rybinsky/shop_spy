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
| ⚙️ **Панель разработчика** | Мониторинг пользователей, товаров и статистики |

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

### 6. Использование

1. Откройте любой товар на Wildberries или Ozon
2. Нажмите на иконку расширения ShopSpy
3. Авторизуйтесь через Telegram (введите Chat ID)
4. Нажмите "Отслеживать" для получения уведомлений о снижении цены

---

## ⚙️ Конфигурация

### Переменные окружения

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `TELEGRAM_BOT_TOKEN` | Токен Telegram бота | — |
| `GEMINI_API_KEY` | API ключ Google Gemini (бесплатно) | — |
| `ANTHROPIC_API_KEY` | API ключ Claude (платно) | — |
| `CRAWL_INTERVAL` | Интервал проверки цен (сек) | `21600` (6 ч) |
| `CRAWLER_TIMEOUT` | Таймаут запросов краулера (сек) | `10` |
| `REQUEST_DELAY` | Задержка между запросами (сек) | `2.0` |
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

При открытии товара на WB или Ozon нажмите на иконку расширения:

```
┌─────────────────────────────────┐
│ 🔍 ShopSpy                      │
│    Отслеживание цен             │
├─────────────────────────────────┤
│ 📍 Текущий товар                │
│ ┌─────────────────────────────┐ │
│ │ 🟣 Wildberries              │ │
│ │ Название товара             │ │
│ │ 1 299 ₽                     │ │
│ │ [👁️ Отслеживать]            │ │
│ └─────────────────────────────┘ │
├─────────────────────────────────┤
│ 📦 Мои товары                   │
│ · 🟣 Товар 1      1 299 ₽      │
│ · 🔵 Товар 2        999 ₽      │
└─────────────────────────────────┘
```

### Команды Telegram-бота

| Команда | Описание |
|---------|----------|
| `/start` | Показать Chat ID и зарегистрироваться |
| `/list` | Отслеживаемые товары |
| `/stop` | Отключить уведомления |
| `/help` | Справка |

---

## 🛠️ Руководство разработчика

### Структура проекта

```
shopspy/
├── backend/
│   ├── main.py              # Точка входа FastAPI
│   ├── config.py            # Конфигурация (dataclasses)
│   ├── api/
│   │   └── routes.py        # API endpoints
│   ├── db/
│   │   ├── database.py      # SQLite connection manager
│   │   └── repositories/
│   │       ├── prices.py    # Репозиторий цен
│   │       ├── alerts.py    # Репозиторий уведомлений
│   │       └── users.py     # Репозиторий пользователей
│   ├── models/
│   │   └── schemas.py       # Pydantic модели
│   ├── services/
│   │   ├── crawler.py       # Фоновый сборщик цен
│   │   ├── price_analyzer.py # Анализ цен
│   │   └── ai_analyzer.py   # AI-анализ отзывов
│   ├── telegram_bot/
│   │   └── bot.py           # Telegram бот
│   └── utils/
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
│       ├── popup.html
│       └── popup.js
├── templates/
│   ├── dashboard.html       # Пользовательский дашборд
│   └── admin.html           # Панель разработчика
├── data/                     # SQLite база
├── requirements.txt
└── README.md
```

### Панель разработчика

Доступна по адресу `/admin`. Позволяет:

- **Просматривать статистику**: пользователи, товары, записи цен, отслеживания
- **Мониторить конфигурацию**: интервал краулера, AI провайдер, статус Telegram
- **Управлять пользователями**: список всех пользователей, их статусы, количество отслеживаний
- **Просматривать отслеживания**: все активные алерты с ценами и целевыми значениями
- **Следить за активностью**: последние записи цен и созданные отслеживания
- **Запускать краулер вручную**: кнопка для принудительного обновления цен

### API Endpoints

#### Пользовательские

| Метод | Endpoint | Описание |
|-------|----------|----------|
| `GET` | `/api/price/history` | История цен товара |
| `POST` | `/api/price` | Записать цену |
| `POST` | `/api/reviews/analyze` | AI-анализ отзывов |
| `POST` | `/api/alerts` | Создать отслеживание |
| `GET` | `/api/alerts` | Список отслеживаний |
| `DELETE` | `/api/alerts` | Удалить отслеживание |
| `GET` | `/api/telegram/status` | Статус пользователя |
| `GET` | `/api/stats` | Общая статистика |
| `GET` | `/api/products` | Список товаров |

#### Административные

| Метод | Endpoint | Описание |
|-------|----------|----------|
| `GET` | `/api/admin/stats` | Детальная статистика |
| `GET` | `/api/admin/users` | Все пользователи |
| `GET` | `/api/admin/alerts` | Все отслеживания |
| `POST` | `/api/crawl` | Запустить краулер |
| `GET` | `/health` | Health check |
| `HEAD` | `/health` | Health check (UptimeRobot) |

---

## 🚢 Деплой на Render.com

### Настройка

1. Создайте Web Service на [Render](https://render.com)
2. Подключите GitHub репозиторий
3. Добавьте переменные окружения:
   - `TELEGRAM_BOT_TOKEN`
   - `GEMINI_API_KEY`
   - `ENVIRONMENT=production`

### Проблема Cold Start

На бесплатном тарифе Render сервер "засыпает" после 15 минут неактивности. Первый запрос занимает 30-60 секунд.

### Решение: UptimeRobot (бесплатно)

1. Зарегистрируйтесь на [UptimeRobot](https://uptimerobot.com)
2. Создайте монитор типа **HTTP(s)**
3. URL: `https://ваш-приложение.onrender.com/health`
4. Interval: **5 минут**

Сервер будет постоянно просыпаться по пингам и не уйдёт в сон.

**Важно:** Бесплатный тариф Render даёт 750 часов/месяц, чего хватает на весь месяц (720 часов).

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

### После деплоя

Обновите `extension/popup/popup.js`:

```javascript
const API_BASE = "https://ваш-приложение.onrender.com";
```

Пересоберите и переустановите расширение.

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