# 🔍 ShopSpy — AI-помощник для умных покупок

**ShopSpy** — браузерное расширение с бэкендом для отслеживания цен на Wildberries и Ozon. Помогает экономить, обнаруживать фейковые скидки и получать уведомления о снижении цен в Telegram.

---

## 📋 Возможности

| Функция | Описание |
|---------|----------|
| 💰 **Три цены** | Отслеживание обычной цены, цены по карте/кошельку и зачёркнутой |
| 📊 **История цен** | Автоматический сбор цен при просмотре товаров |
| 🚨 **Детектор фейковых скидок** | Анализ реальности скидки на основе истории |
| 🤖 **AI-анализ отзывов** | Краткая выжимка плюсов и минусов товара |
| 📱 **Telegram-уведомления** | Оповещения о снижении цен |
| 🎯 **Целевые цены** | Уведомление когда цена достигнет желаемого уровня |
| 📈 **График истории** | Визуализация динамики цен с двумя линиями |
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

## 💰 Отслеживание трёх цен

ShopSpy автоматически собирает три типа цен для каждого товара:

### Wildberries

| Цена | Описание | Цвет в UI |
|------|----------|-----------|
| **Обычная цена** | Цена без WB Кошелька | Белый |
| **WB Кошелёк** | Цена с кошельком (самая низкая) | Фиолетовый |
| **Зачёркнутая** | "Оригинальная" цена до скидки | Серый с зачёркиванием |

### Ozon

| Цена | Описание | Цвет в UI |
|------|----------|-----------|
| **Обычная цена** | Цена без Ozon Банка | Белый |
| **Ozon Банк** | Цена по карте (самая низкая) | Синий |
| **Зачёркнутая** | "Оригинальная" цена до скидки | Серый с зачёркиванием |

### Как это помогает

- **Видите реальную экономию** — насколько дешевле с картой/кошельком
- **Детектируете манипуляции** — зачёркнутая цена часто прыгает
- **Принимаете взвешенное решение** — все данные перед глазами

---

## ⚙️ Конфигурация

### Переменные окружения

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `TELEGRAM_BOT_TOKEN` | Токен Telegram бота | — |
| `GEMINI_API_KEY` | API ключ Google Gemini (бесплатно) | — |
| `ANTHROPIC_API_KEY` | API ключ Claude (платно) | — |
| `RATE_LIMIT_PER_IP` | Лимит AI-запросов в день на IP | `10` |
| `RATE_LIMIT_GLOBAL` | Глобальный лимит AI-запросов | `200` |
| `ENVIRONMENT` | Окружение: `development` / `production` | `development` |
| `PORT` | Порт сервера | `8000` |

### Настройки анализа цен

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `ANALYSIS_CLICKBAIT_THRESHOLD` | % скидки = кликбейт | `80` |
| `ANALYSIS_FAKE_DISCOUNT_THRESHOLD` | % заявленной скидки для проверки | `30` |
| `ANALYSIS_GOOD_DEAL_THRESHOLD` | % ниже средней = хорошая сделка | `15` |
| `ANALYSIS_HISTORY_DAYS` | Дней истории для анализа | `30` |
| `ANALYSIS_MIN_RECORDS` | Минимум записей для анализа | `2` |

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

При открытии товара на WB или Ozon справа появится панель ShopSpy:

```
┌─────────────────────────────────────┐
│ 🔍 ShopSpy                          │
├─────────────────────────────────────┤
│ 💰 Текущие цены                     │
│   💜 WB Кошелёк: 19 870 ₽  -58%    │
│   36 026 ₽  ~~48 100 ₽  -25%       │
│   💰 С кошельком экономия 45%       │
├─────────────────────────────────────┤
│ 📊 Анализ цены                      │
│   ✅ Хорошая цена!                  │
│   Цена близка к минимуму            │
├─────────────────────────────────────┤
│ 📈 История цен (14 точек)           │
│   [График с двумя линиями]          │
│   мин: 34 500 ₽  сред: 36 000 ₽    │
│   макс: 42 000 ₽                    │
├─────────────────────────────────────┤
│ 🔔 Отслеживание                     │
│   [🔔 Отслеживать]                  │
├─────────────────────────────────────┤
│ 🤖 AI-анализ отзывов                │
│   [Анализировать отзывы]            │
└─────────────────────────────────────┘
```

### Что показывает анализ

**Verdict'ы (вердикты):**

| Статус | Значение |
|--------|----------|
| ✅ **good_deal** | Хорошая цена, можно брать |
| 🚨 **fake_discount** | Фейковая скидка, заявлено больше чем есть |
| ⚠️ **overpriced** | Цена завышена, лучше подождать |
| ℹ️ **normal** | Обычная цена, ничего особенного |
| 📊 **insufficient_data** | Недостаточно данных, зайдите ещё |

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
│   ├── config.py            # Конфигурация (env vars)
│   ├── api/
│   │   └── routes.py        # API endpoints
│   ├── db/
│   │   ├── database.py      # SQLite connection manager
│   │   └── repositories/
│   │       ├── prices.py    # Репозиторий цен
│   │       ├── alerts.py    # Репозиторий уведомлений
│   │       └── users.py     # Репозиторий пользователей
│   ├── models/
│   │   └── schemas.py       # Pydantic модели (API)
│   ├── services/
│   │   ├── price_analyzer.py # Анализ цен и детекция скидок
│   │   └── ai_analyzer.py   # AI-анализ отзывов
│   ├── telegram_bot/
│   │   └── bot.py           # Telegram бот
│   └── utils/
│       └── logging.py       # Настройка логирования
├── extension/
│   ├── manifest.json
│   ├── config.js            # API_BASE адрес бэкенда
│   ├── content/
│   │   ├── shared.js        # Общий код (UI, API, график)
│   │   ├── wb.js            # Парсер Wildberries
│   │   ├── ozon.js          # Парсер Ozon
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

### Архитектура данных

```
Пользователь заходит на товар
         ↓
Content script парсит 3 цены
         ↓
POST /api/price → сохранение в SQLite
         ↓
GET /api/price/history
         ↓
PriceAnalyzer.analyze():
  - вычисляет min/max/avg
  - детектит манипуляции
  - определяет verdict
         ↓
Frontend рисует UI
```

### Таблица prices (БД)

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | INTEGER | Primary Key |
| `platform` | TEXT | 'wb' или 'ozon' |
| `product_id` | TEXT | ID товара на площадке |
| `product_name` | TEXT | Название |
| `price` | REAL | Цена без карты/кошелька |
| `original_price` | REAL | Зачёркнутая "оригинальная" цена |
| `card_price` | REAL | Цена по карте/кошельку |
| `url` | TEXT | URL товара |
| `recorded_at` | TIMESTAMP | Время записи |

### Панель разработчика

Доступна по адресу `/admin`. Позволяет:

- Просматривать статистику
- Мониторить конфигурацию
- Управлять пользователями
- Просматривать отслеживания

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
| `GET` | `/health` | Health check |

---

## 🚢 Деплой на Render.com

### Шаг 1: Создание Web Service

1. Зарегистрируйтесь на [Render](https://render.com)
2. Нажмите **New → Web Service**
3. Подключите GitHub репозиторий

### Шаг 2: Настройка

| Параметр | Значение |
|----------|----------|
| Name | `shopspy` |
| Environment | `Python 3` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `python -m backend.main` |
| Instance Type | `Free` |

### Шаг 3: Переменные окружения

Добавьте в раздел **Environment Variables**:

```
TELEGRAM_BOT_TOKEN=your_bot_token
GEMINI_API_KEY=your_gemini_key
ENVIRONMENT=production
```

### Шаг 4: UptimeRobot (чтобы не засыпал)

На бесплатном тарифе Render "засыпает" через 15 минут неактивности.

1. Зарегистрируйтесь на [UptimeRobot](https://uptimerobot.com)
2. **Add New Monitor**:
   - Monitor Type: HTTP(s)
   - URL: `https://ваш-приложение.onrender.com/health`
   - Monitoring Interval: 5 минут
3. Сервер будет постоянно активен

### Шаг 5: Обновление расширения

После деплоя измените `extension/config.js`:

```javascript
const SHOPSPY_CONFIG = {
  API_BASE: "https://ваш-приложение.onrender.com",
};
```

Перезагрузите расширение в `chrome://extensions/`.

### render.yaml (опционально)

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

---

## 🔧 Настройка анализа цен

Все пороги анализа вынесены в переменные окружения. Меняйте их без изменения кода:

### Примеры настроек

**Консервативный режим** (только очевидные скидки):
```
ANALYSIS_CLICKBAIT_THRESHOLD=90
ANALYSIS_FAKE_DISCOUNT_THRESHOLD=50
ANALYSIS_GOOD_DEAL_THRESHOLD=20
```

**Агрессивный режим** (больше уведомлений):
```
ANALYSIS_CLICKBAIT_THRESHOLD=70
ANALYSIS_FAKE_DISCOUNT_THRESHOLD=20
ANALYSIS_GOOD_DEAL_THRESHOLD=10
```

---

## 📊 API Reference

### Запись цены

```http
POST /api/price
Content-Type: application/json

{
    "platform": "wb",
    "product_id": "12345678",
    "product_name": "Товар",
    "price": 36026,
    "original_price": 48100,
    "card_price": 19870,
    "url": "https://..."
}
```

### Получение истории

```http
GET /api/price/history?platform=wb&product_id=12345678

Response: {
    "history": [
        {
            "price": 36026,
            "original_price": 48100,
            "card_price": 19870,
            "recorded_at": "2024-01-15T10:00:00"
        }
    ],
    "analysis": {
        "verdict": "good_deal",
        "message": "✅ Цена близка к минимуму",
        "current_price": 36026,
        "min_price": 34500,
        "max_price": 42000,
        "avg_price": 36000,
        "card_price": 19870,
        "min_card_price": 18500,
        "claimed_discount": 25,
        "real_discount_from_avg": 0
    }
}
```

### AI-анализ отзывов

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
        "verdict": "Хороший товар",
        "buy_recommendation": "yes"
    }
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

- [x] Отслеживание трёх цен (обычная, карта, зачёркнутая)
- [x] График с двумя линиями
- [x] Детектор фейковых скидок
- [ ] Детектор манипуляций с original_price
- [ ] Детектор кликбейт-цен
- [ ] Сравнение цен между WB, Ozon, Яндекс.Маркет
- [ ] Детектор накрученных отзывов
- [ ] Прогнозирование цен
- [ ] Мобильное приложение

---

<p align="center">
  Сделано с ❤️ для умных покупателей
</p>