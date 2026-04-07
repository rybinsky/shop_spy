import asyncio
from playwright.async_api import async_playwright


async def fetch_price(url: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,  # важно! сначала false
            args=["--disable-blink-features=AutomationControlled"]
        )

        context = await browser.new_context()
        page = await context.new_page()

        print(f"[INFO] Opening {url}")
        await page.goto(url, timeout=60000)

        # ДАЁМ ВРЕМЯ на JS и возможную капчу
        await page.wait_for_timeout(5000)

        # 👉 если есть капча — реши вручную
        print("[INFO] If captcha appears — solve it manually...")

        # ждём появления цены
        try:
            await page.wait_for_selector("[data-widget='webPrice']", timeout=15000)
        except:
            print("[ERROR] Price selector not found")
            html = await page.content()
            print(html[:1000])
            await browser.close()
            return None

        # достаём цену
        price_element = await page.query_selector("[data-widget='webPrice']")
        price_text = await price_element.inner_text()

        print(f"[SUCCESS] Price: {price_text}")

        await browser.close()
        return price_text


if __name__ == "__main__":
    url = "https://www.ozon.ru/product/1788753655/"
    asyncio.run(fetch_price(url))