"""
ShopSpy - Фоновый сборщик цен
Обходит все ранее просмотренные товары и обновляет цены через публичные API маркетплейсов.
"""

import asyncio
import json
import sqlite3
import os
import logging
from datetime import datetime, timedelta
from contextlib import contextmanager

import httpx

logger = logging.getLogger("shopspy.crawler")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", "%H:%M:%S"))
    logger.addHandler(handler)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "shopspy.db")

CRAWL_INTERVAL = int(os.environ.get("CRAWL_INTERVAL", 3600 * 6))  # 6 часов
REQUEST_DELAY = 2.0


def get_db_path():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return DB_PATH


@contextmanager
def get_db():
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def get_tracked_products():
    """Получает список уникальных товаров для обхода."""
    with get_db() as db:
        rows = db.execute(
            """SELECT DISTINCT platform, product_id, product_name, url
               FROM prices
               ORDER BY recorded_at DESC"""
        ).fetchall()
    return [dict(r) for r in rows]


def save_price(platform, product_id, product_name, price, original_price=None, url=None):
    """Сохраняет цену, пропуская дубликаты."""
    with get_db() as db:
        last = db.execute(
            """SELECT price, recorded_at FROM prices
               WHERE platform=? AND product_id=?
               ORDER BY recorded_at DESC LIMIT 1""",
            (platform, product_id)
        ).fetchone()

        if last:
            if abs(last["price"] - price) < 0.01:
                last_dt = datetime.fromisoformat(last["recorded_at"])
                if datetime.now() - last_dt < timedelta(hours=6):
                    return False

        db.execute(
            """INSERT INTO prices (platform, product_id, product_name, price, original_price, url)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (platform, product_id, product_name, price, original_price, url)
        )
        return True


async def fetch_wb_price(client, product_id):
    """Получает цену товара через публичный API Wildberries."""
    url = f"https://card.wb.ru/cards/v2/detail?appType=1&curr=rub&dest=-1257786&nm={product_id}"

    try:
        resp = await client.get(url, timeout=10)
        if resp.status_code != 200:
            return None

        data = resp.json()
        products = data.get("data", {}).get("products", [])
        if not products:
            return None

        product = products[0]
        price = product.get("salePriceU", 0) / 100
        original = product.get("priceU", 0) / 100
        name = product.get("name", "")

        if price <= 0:
            return None

        return {
            "price": price,
            "original_price": original if original > price else None,
            "name": name
        }
    except Exception as e:
        logger.debug(f"WB API error for {product_id}: {e}")
        return None


async def fetch_ozon_price(client, product_id):
    """Пробует получить цену с Ozon (менее надежно чем WB)."""
    try:
        url = f"https://www.ozon.ru/api/entrypoint-api.bx/page/json/v2?url=/product/{product_id}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        }
        resp = await client.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return None

        data = resp.json()
        price = _find_price_in_dict(data)
        if price and price > 0:
            return {"price": price, "original_price": None, "name": ""}
    except Exception as e:
        logger.debug(f"Ozon API error for {product_id}: {e}")

    return None


def _find_price_in_dict(d, depth=0):
    """Рекурсивно ищет цену в JSON."""
    if depth > 8:
        return None
    if isinstance(d, dict):
        for key in ("price", "finalPrice", "cardPrice"):
            if key in d:
                val = d[key]
                if isinstance(val, (int, float)) and val > 0:
                    return float(val)
                if isinstance(val, str):
                    clean = val.replace("\u2009", "").replace(" ", "").replace(",", ".").replace("₽", "")
                    try:
                        v = float(clean)
                        if v > 0:
                            return v
                    except ValueError:
                        pass
        for v in d.values():
            result = _find_price_in_dict(v, depth + 1)
            if result:
                return result
    elif isinstance(d, list):
        for item in d[:15]:
            result = _find_price_in_dict(item, depth + 1)
            if result:
                return result
    return None


async def crawl_once():
    """Один обход всех отслеживаемых товаров."""
    products = get_tracked_products()
    if not products:
        logger.info("Нет товаров для обхода")
        return

    seen = set()
    unique = []
    for p in products:
        key = f"{p['platform']}:{p['product_id']}"
        if key not in seen:
            seen.add(key)
            unique.append(p)

    logger.info(f"Обход {len(unique)} товаров...")
    updated = 0
    errors = 0

    async with httpx.AsyncClient(
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        follow_redirects=True
    ) as client:
        for product in unique:
            platform = product["platform"]
            pid = product["product_id"]

            try:
                if platform == "wb":
                    result = await fetch_wb_price(client, pid)
                elif platform == "ozon":
                    result = await fetch_ozon_price(client, pid)
                else:
                    continue

                if result and result["price"] > 0:
                    name = result.get("name") or product.get("product_name", "")
                    saved = save_price(
                        platform=platform,
                        product_id=pid,
                        product_name=name,
                        price=result["price"],
                        original_price=result.get("original_price"),
                        url=product.get("url")
                    )
                    if saved:
                        updated += 1
                else:
                    errors += 1
            except Exception as e:
                errors += 1
                logger.debug(f"Ошибка {platform}:{pid}: {e}")

            await asyncio.sleep(REQUEST_DELAY)

    logger.info(f"Обход завершен: обновлено {updated}, ошибок {errors}, всего {len(unique)}")


async def crawl_loop():
    """Бесконечный цикл обхода."""
    await asyncio.sleep(30)
    logger.info(f"Краулер запущен. Интервал: {CRAWL_INTERVAL // 3600} ч.")

    while True:
        try:
            await crawl_once()
        except Exception as e:
            logger.error(f"Ошибка краулера: {e}")

        logger.info(f"Следующий обход через {CRAWL_INTERVAL // 3600} ч.")
        await asyncio.sleep(CRAWL_INTERVAL)