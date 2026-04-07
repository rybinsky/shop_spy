"""
Quick test: fetch WB product price via Playwright scraper.
Usage: python test_playwright.py [product_id]
Default product_id: 303802221 (the one that returns 403)
"""

import asyncio
import sys

from backend.utils.marketplace_api import get_scraper


async def main():
    product_id = sys.argv[1] if len(sys.argv) > 1 else "303802221"
    print(f"Fetching WB product {product_id} via Playwright...")

    scraper = get_scraper()
    try:
        result = await scraper.fetch_wb_price(product_id)
        if result:
            print(f"\nName:           {result['name']}")
            print(f"Price:          {result['price']:,.0f} ₽")
            if result["original_price"]:
                print(f"Original price: {result['original_price']:,.0f} ₽")
            print("\nOK")
        else:
            print("\nFailed: no price data returned")
    finally:
        await scraper.close()


if __name__ == "__main__":
    asyncio.run(main())
