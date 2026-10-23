import asyncio
from playwright.async_api import async_playwright, Error

async def run():
    print("Попытка запуска Playwright с логами и --no-sandbox...")
    try:
        async with async_playwright() as p:
            print("Запускаем Chromium...")
            # Добавляем аргумент --no-sandbox и увеличиваем таймаут запуска
            browser = await p.chromium.launch(
                headless=False, # По-прежнему пытаемся увидеть окно, если возможно
                args=['--no-sandbox', '--disable-setuid-sandbox'], # Важные аргументы для WSL
                timeout=60000 # Увеличиваем таймаут до 60 секунд
            )
            print(f"Браузер запущен: {browser.version}")
            page = await browser.new_page()
            print(f"Переходим на https://www.example.com...")
            await page.goto("https://www.example.com", wait_until="networkidle", timeout=60000) # Увеличиваем таймаут навигации
            print(f"Загружена страница: {await page.title()}")
            html_content = await page.content()
            print(f"HTML-контент (первые 500 символов):\n{html_content[:500]}...")
            await browser.close()
            print("Браузер закрыт.")
    except Error as e:
        print(f"Ошибка Playwright: {e}")
    except Exception as e:
        print(f"Неизвестная ошибка: {e}")

if __name__ == '__main__':
    asyncio.run(run())