"""
ShopSpy - AI-помощник покупателя маркетплейсов
Локальный бэкенд на FastAPI + SQLite
"""

import os
import json
import sqlite3
import hashlib
from datetime import datetime, timedelta
from contextlib import contextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
import httpx
import uvicorn
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    force=True
)
logger = logging.getLogger(__name__)


app = FastAPI(title="ShopSpy API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Rate limiting ─────────────────────────────────────────

RATE_LIMIT_PER_IP = int(os.environ.get("RATE_LIMIT_PER_IP", 10))   # запросов/день с одного IP
RATE_LIMIT_GLOBAL = int(os.environ.get("RATE_LIMIT_GLOBAL", 200))  # запросов/день всего

_rate_data: dict[str, dict] = {}  # { ip: {count, date} }
_global_rate: dict = {"count": 0, "date": None}


def _check_rate_limit(ip: str):
    today = datetime.now().date().isoformat()

    # Глобальный лимит
    if _global_rate["date"] != today:
        _global_rate["count"] = 0
        _global_rate["date"] = today
    if _global_rate["count"] >= RATE_LIMIT_GLOBAL:
        raise HTTPException(status_code=429, detail="Глобальный дневной лимит AI-запросов исчерпан. Попробуйте завтра.")

    # Лимит по IP
    entry = _rate_data.get(ip)
    if not entry or entry["date"] != today:
        _rate_data[ip] = {"count": 0, "date": today}
        entry = _rate_data[ip]
    if entry["count"] >= RATE_LIMIT_PER_IP:
        raise HTTPException(status_code=429, detail=f"Лимит {RATE_LIMIT_PER_IP} AI-запросов в день с вашего IP исчерпан.")

    entry["count"] += 1
    _global_rate["count"] += 1


# ─────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "shopspy.db")
CLAUDE_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyDqLaNUl8xf94CAvvb-7ueQFJTFN_dcWDE")
API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")


def get_llm_key():
    """Возвращает (provider, key). Gemini приоритетнее - он бесплатный."""
    if GEMINI_API_KEY:
        return ("gemini", GEMINI_API_KEY)
    if CLAUDE_API_KEY:
        return ("claude", CLAUDE_API_KEY)
    return (None, None)


# ── Database ──────────────────────────────────────────────

def get_db_path():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return DB_PATH


def init_db():
    path = get_db_path()
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,
            product_id TEXT NOT NULL,
            product_name TEXT,
            price REAL NOT NULL,
            original_price REAL,
            url TEXT,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_prices_product
        ON prices(platform, product_id);

        CREATE TABLE IF NOT EXISTS reviews_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,
            product_id TEXT NOT NULL,
            summary TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_reviews_product
        ON reviews_cache(platform, product_id);
    """)
    conn.close()


@contextmanager
def get_db():
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


init_db()


# ── Models ────────────────────────────────────────────────

class PriceRecord(BaseModel):
    platform: str  # "wb" | "ozon" | "yandex"
    product_id: str
    product_name: Optional[str] = None
    price: float
    original_price: Optional[float] = None
    url: Optional[str] = None


class ReviewsRequest(BaseModel):
    platform: str
    product_id: str
    product_name: str
    reviews: list[str]  # список текстов отзывов


class CompareRequest(BaseModel):
    product_name: str


# ── Price endpoints ───────────────────────────────────────

@app.post("/api/price")
def record_price(record: PriceRecord):
    """Расширение отправляет текущую цену товара."""
    with get_db() as db:
        # Не записываем дубликат если цена не изменилась за последний час
        last = db.execute(
            """SELECT price FROM prices
               WHERE platform=? AND product_id=?
               ORDER BY recorded_at DESC LIMIT 1""",
            (record.platform, record.product_id)
        ).fetchone()

        if last and abs(last["price"] - record.price) < 0.01:
            # Проверяем давность последней записи
            last_time = db.execute(
                """SELECT recorded_at FROM prices
                   WHERE platform=? AND product_id=?
                   ORDER BY recorded_at DESC LIMIT 1""",
                (record.platform, record.product_id)
            ).fetchone()
            if last_time:
                last_dt = datetime.fromisoformat(last_time["recorded_at"])
                if datetime.now() - last_dt < timedelta(hours=6):
                    return {"status": "skipped", "reason": "same_price_recent"}

        db.execute(
            """INSERT INTO prices (platform, product_id, product_name, price, original_price, url)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (record.platform, record.product_id, record.product_name,
             record.price, record.original_price, record.url)
        )

    return {"status": "ok"}


@app.get("/api/price/history")
def get_price_history(platform: str, product_id: str):
    """История цен для графика."""
    with get_db() as db:
        rows = db.execute(
            """SELECT price, original_price, recorded_at
               FROM prices
               WHERE platform=? AND product_id=?
               ORDER BY recorded_at ASC""",
            (platform, product_id)
        ).fetchall()

    history = [
        {
            "price": r["price"],
            "original_price": r["original_price"],
            "date": r["recorded_at"]
        }
        for r in rows
    ]

    # Анализ фейковой скидки
    analysis = analyze_discount(history)

    return {"history": history, "analysis": analysis}


def analyze_discount(history: list[dict]) -> dict:
    """Анализирует историю цен и определяет фейковую скидку."""
    if len(history) < 2:
        return {"verdict": "insufficient_data", "message": "Недостаточно данных для анализа"}

    prices = [h["price"] for h in history]
    current = prices[-1]
    avg_price = sum(prices) / len(prices)
    min_price = min(prices)
    max_price = max(prices)

    # Проверяем был ли резкий рост перед текущей "скидкой"
    if len(prices) >= 3:
        recent_max = max(prices[-5:]) if len(prices) >= 5 else max(prices)
        if recent_max > avg_price * 1.3 and current <= avg_price:
            return {
                "verdict": "fake_discount",
                "message": f"Подозрительно! Цена была завышена до {recent_max:.0f} руб перед скидкой. Средняя цена: {avg_price:.0f} руб.",
                "avg_price": round(avg_price),
                "current": round(current),
                "savings_real": round(avg_price - current) if current < avg_price else 0
            }

    if current < avg_price * 0.85:
        return {
            "verdict": "good_deal",
            "message": f"Хорошая цена! На {round((1 - current/avg_price) * 100)}% ниже средней ({avg_price:.0f} руб).",
            "avg_price": round(avg_price),
            "current": round(current),
            "savings_real": round(avg_price - current)
        }

    if current > avg_price * 1.1:
        return {
            "verdict": "overpriced",
            "message": f"Сейчас дороже обычного на {round((current/avg_price - 1) * 100)}%. Средняя цена: {avg_price:.0f} руб. Лучше подождать.",
            "avg_price": round(avg_price),
            "current": round(current),
            "savings_real": 0
        }

    return {
        "verdict": "normal",
        "message": f"Обычная цена. Средняя: {avg_price:.0f} руб.",
        "avg_price": round(avg_price),
        "current": round(current),
        "savings_real": 0
    }


# ── AI Review Analysis ────────────────────────────────────

@app.post("/api/reviews/analyze")
async def analyze_reviews(req: ReviewsRequest, request: Request):
    """AI-анализ отзывов через Gemini (бесплатно) или Claude API."""
    ip = request.headers.get("x-forwarded-for", request.client.host).split(",")[0].strip()
    _check_rate_limit(ip)
    
    provider, api_key = get_llm_key()
    if not provider:
        return {
            "summary": {
                "pros": ["API ключ не настроен"],
                "cons": ["Получите бесплатный ключ на ai.google.dev"],
                "verdict": "Добавьте GEMINI_API_KEY (бесплатно, без карты) в переменные окружения на Render",
                "rating_honest": None,
                "buy_recommendation": "unknown"
            }
        }

    # Проверяем кэш
    with get_db() as db:
        cached = db.execute(
            """SELECT summary FROM reviews_cache
               WHERE platform=? AND product_id=?
               AND created_at > datetime('now', '-24 hours')
               ORDER BY created_at DESC LIMIT 1""",
            (req.platform, req.product_id)
        ).fetchone()

    if cached:
        return {"summary": json.loads(cached["summary"])}

    # Берем до 30 отзывов для анализа
    reviews_text = "\n---\n".join(req.reviews[:30])

    prompt = f"""Проанализируй отзывы покупателей на товар "{req.product_name}".

Отзывы:
{reviews_text}

Ответь строго в JSON без маркдауна и backticks:
{{
  "pros": ["плюс 1", "плюс 2", "плюс 3"],
  "cons": ["минус 1", "минус 2", "минус 3"],
  "verdict": "краткий вердикт в 1-2 предложения",
  "rating_honest": 4.2,
  "buy_recommendation": "yes/no/wait",
  "fake_reviews_detected": false,
  "fake_reviews_reason": "причина если обнаружены накрученные отзывы"
}}

Пиши "е" вместо "ё". Будь честным и критичным."""
    try:
        if provider == "gemini":
            summary = await _call_gemini(api_key, prompt)
        else:
            summary = await _call_claude(api_key, prompt)
    except Exception as e:
        summary = {
            "pros": [],
            "cons": [],
            "verdict": f"Ошибка анализа: {str(e)}",
            "rating_honest": None,
            "buy_recommendation": "unknown"
        }

    # Кэшируем
    with get_db() as db:
        db.execute(
            "INSERT INTO reviews_cache (platform, product_id, summary) VALUES (?, ?, ?)",
            (req.platform, req.product_id, json.dumps(summary, ensure_ascii=False))
        )

    return {"summary": summary}


def _parse_llm_response(text: str) -> dict:
    """Парсит JSON из ответа LLM, убирая маркдаун обертки."""
    import re
    
    text = text.strip()
    # Убираем ```json ... ```
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    text = text.strip()
    
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        # Логируем ошибку и полный текст от LLM
        print(f"\n{'='*60}")
        print(f"JSON DECODE ERROR: {e}")
        print(f"{'='*60}")
        print(f"FULL RAW TEXT FROM LLM:")
        print(text)
        print(f"{'='*60}\n")
        
        # Пытаемся починить обрезанный JSON
        if "Unterminated string" in str(e):
            pos = getattr(e, 'pos', len(text))
            fixed = text[:pos] + '"'
            
            # Считаем и закрываем открытые скобки
            open_braces = fixed.count('{') - fixed.count('}')
            open_brackets = fixed.count('[') - fixed.count(']')
            fixed += ']' * open_brackets + '}' * open_braces
            
            print(f"Attempting to repair JSON (closing string at pos {pos})...")
            
            try:
                result = json.loads(fixed)
                print(f"JSON REPAIRED SUCCESSFULLY!")
                return result
            except Exception as fix_err:
                print(f"Failed to repair JSON: {fix_err}")
        
        # Извлекаем данные через regex как fallback
        print(f"Using regex fallback extraction...")
        verdict_match = re.search(r'"verdict"\s*:\s*"([^"]*)"', text)
        rating_match = re.search(r'"rating_honest"\s*:\s*([\d.]+)', text)
        print(f"  extracted verdict: {verdict_match.group(1) if verdict_match else 'NOT FOUND'}")
        print(f"  extracted rating: {rating_match.group(1) if rating_match else 'NOT FOUND'}")
        
        return {
            "pros": [],
            "cons": [],
            "verdict": verdict_match.group(1) if verdict_match else f"Ошибка парсинга: {str(e)}",
            "rating_honest": float(rating_match.group(1)) if rating_match else None,
            "buy_recommendation": "unknown"
        }




async def _call_gemini(api_key: str, prompt: str) -> dict:
    """Вызов Google Gemini API (бесплатный)."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={api_key}"
    print("SBVIBIBSUVISBVIUBV")
    async with httpx.AsyncClient(timeout=30) as client:
        logger.info("="*60)
        logger.info("CALLING GEMINI API...")
        
        resp = await client.post(url, json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 1000
            }
        })
        data = resp.json()
        
        logger.info("="*60)
        logger.info(f"GEMINI API RESPONSE Status: {resp.status_code}")
        logger.info(f"GEMINI API RESPONSE Data: {data}")
        logger.info("="*60)
        
        # Проверяем на ошибку
        if "error" in data:
            logger.error(f"Gemini API error: {data['error']}")
            raise Exception(f"Gemini API error: {data['error']}")
        
        if "candidates" not in data:
            logger.error(f"No candidates in response: {data}")
            raise Exception(f"No candidates in response: {data}")
        
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return _parse_llm_response(text)



async def _call_claude(api_key: str, prompt: str) -> dict:
    """Вызов Claude API."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01"
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": prompt}]
            }
        )
        data = resp.json()
        text = "".join(
            block["text"] for block in data.get("content", [])
            if block.get("type") == "text"
        )
        return _parse_llm_response(text)


# ── Stats ─────────────────────────────────────────────────

@app.get("/api/stats")
def get_stats():
    """Статистика по собранным данным."""
    with get_db() as db:
        total_prices = db.execute("SELECT COUNT(*) as c FROM prices").fetchone()["c"]
        unique_products = db.execute(
            "SELECT COUNT(DISTINCT platform || product_id) as c FROM prices"
        ).fetchone()["c"]
        platforms = db.execute(
            "SELECT platform, COUNT(DISTINCT product_id) as products FROM prices GROUP BY platform"
        ).fetchall()

    return {
        "total_records": total_prices,
        "unique_products": unique_products,
        "platforms": {r["platform"]: r["products"] for r in platforms}
    }


@app.get("/api/products")
def get_tracked_products(limit: int = 50):
    """Список отслеживаемых товаров."""
    with get_db() as db:
        rows = db.execute(
            """SELECT platform, product_id, product_name, url,
                      MIN(price) as min_price,
                      MAX(price) as max_price,
                      COUNT(*) as records,
                      MAX(recorded_at) as last_seen
               FROM prices
               GROUP BY platform, product_id
               ORDER BY last_seen DESC
               LIMIT ?""",
            (limit,)
        ).fetchall()

    return {
        "products": [
            {
                "platform": r["platform"],
                "product_id": r["product_id"],
                "name": r["product_name"],
                "url": r["url"],
                "min_price": r["min_price"],
                "max_price": r["max_price"],
                "records": r["records"],
                "last_seen": r["last_seen"]
            }
            for r in rows
        ]
    }


# ── Dashboard ─────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def dashboard():
    """Веб-дашборд для просмотра собранных данных."""
    html_path = os.path.join(BASE_DIR, "templates", "dashboard.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()


# ── Run ───────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print("\n" + "=" * 50)
    print("  ShopSpy - AI-помощник покупателя")
    print("=" * 50)
    print(f"  Дашборд:   http://localhost:{port}")
    print(f"  API docs:  http://localhost:{port}/docs")
    provider, key = get_llm_key()
    ai_status = f"Gemini (бесплатный)" if provider == "gemini" else f"Claude" if provider == "claude" else "НЕ настроен (добавьте GEMINI_API_KEY)"
    print(f"  Claude AI: {ai_status}")
    print("=" * 50 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=port)
