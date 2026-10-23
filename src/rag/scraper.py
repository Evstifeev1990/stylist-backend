# src/rag/scraper.py
import asyncio
from typing import Optional, List, Tuple
from urllib.parse import urljoin, urlparse
import re

from bs4 import BeautifulSoup, Tag
from playwright.async_api import async_playwright, Page, Browser

# --- Вспомогательная функция для парсинга текста ---
def _parse_html_to_text(html_content: str, url: str = "N/A") -> Optional[str]:
    """
    Вспомогательная функция для парсинга текста из HTML без повторного HTTP-запроса.
    Теперь включает более специфичный поиск элементов услуг.
    """
    soup = BeautifulSoup(html_content, 'html.parser')

    # Удаляем ненужные теги для более чистого контента
    for script_or_style in soup(["script", "style", "meta", "noscript", "header", "footer", "nav"]):
        script_or_style.decompose()

    text_parts = []
    found_tags_with_content = set()

    # --- Специфичный подход для извлечения услуг ---
    # Ищем все элементы, которые содержат название услуги, как вы указали
    all_service_name_tags = soup.find_all('div', class_=lambda x: x and 'Services_servicesItemFilledName' in x)
    
    # Собираем данные об услугах в более структурированном виде
    structured_services = []
    processed_elements = [] # Для отслеживания уже обработанных элементов и их родителей

    for name_tag in all_service_name_tags:
        service_name = name_tag.get_text(strip=True)
        if service_name:
            price = None
            # Пытаемся найти родительский контейнер, который, вероятно, содержит и название, и цену
            # Ищем ближайшего родителя, который содержит Services_servicesItem
            # или Service_service__ (если он используется для обертки одной услуги)
            service_container = name_tag.find_parent('div', class_=lambda x: x and ('Services_servicesItem' in x or 'Service_service__' in x))
            
            if service_container:
                # Ищем цену внутри этого контейнера
                price_tag = service_container.find('span', class_=lambda x: x and ('Price' in x or 'price' in x))
                if not price_tag:
                    price_tag = service_container.find('div', class_=lambda x: x and ('Price' in x or 'price' in x))
                
                if price_tag:
                    price = price_tag.get_text(strip=True)
                
                service_entry = f"Услуга: {service_name}"
                if price:
                    service_entry += f" Цена: {price}"
                
                structured_services.append(service_entry)
                found_tags_with_content.add("service_item_structured")
                
                # Добавляем контейнер в список для последующего удаления, чтобы избежать дублирования
                if service_container not in processed_elements:
                    processed_elements.append(service_container)
            else: # Если не нашли специфичный контейнер, добавляем только название
                structured_services.append(f"Услуга: {service_name}")
                found_tags_with_content.add("service_item_name_only")
    
    # Добавляем все найденные структурированные услуги в text_parts
    text_parts.extend(structured_services)

    # Удаляем обработанные контейнеры из soup, чтобы они не попали в общий парсинг
    for el in processed_elements:
        el.decompose()

    # Извлекаем текст из общих смысловых тегов (как запасной вариант и для остального контента)
    tags_to_extract_general = ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'article', 'div', 'span', 'button']
    for tag_name in tags_to_extract_general:
        for tag in soup.find_all(tag_name):
            text = tag.get_text(strip=True)
            if text:
                text_parts.append(text)
                found_tags_with_content.add(tag_name)

    full_text = "\n".join(part for part in text_parts if part)
    full_text = re.sub(r'\n\s*\n', '\n', full_text).strip()

    # --- УСИЛЕННЫЙ ОТЛАДОЧНЫЙ ВЫВОД ---
    print(f"\n--- DEBUG-Скрапер: URL: {url} ---")
    if not full_text:
        print(f"  Не найдено значимого текста из тегов: {', '.join(sorted(list(found_tags_with_content)))}")
    else:
        print(f"  Текст извлечен из тегов: {', '.join(sorted(list(found_tags_with_content)))}")
        print(f"  --- Полный извлеченный текст для URL: {url} ---")
        print(full_text)
        print(f"  --- Конец полного текста (всего {len(full_text)} символов) ---")
    print("------------------------------------\n")
    
    return full_text if full_text else None

# --- Асинхронная функция для скрапинга с Playwright ---
async def scrape_website_with_playwright(url: str, page: Page) -> Optional[str]:
    """
    Парсит отдельную веб-страницу по URL, используя Playwright для рендеринга JavaScript,
    и извлекает текст. Использует уже открытую страницу Playwright.
    """
    try:
        await page.goto(url, wait_until="networkidle", timeout=60000)
        html_content = await page.content()
        return _parse_html_to_text(html_content, url=url)

    except Exception as e:
        print(f"Ошибка Playwright при загрузке или парсинге страницы {url}: {e}")
        return None

# --- Изменена функция _extract_links ---
async def _extract_links(html_content: str, base_url: str) -> List[str]:
    """
    Извлекает все валидные внутренние ссылки из HTML-содержимого страницы.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    links = []
    base_host = urlparse(base_url).netloc

    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href'].strip()

        if href.startswith('#') or href.startswith('javascript:'):
            continue

        full_url = urljoin(base_url, href)
        parsed_url = urlparse(full_url)

        if parsed_url.netloc == base_host:
            if not parsed_url.path.endswith(('.pdf', '.doc', '.docx', '.zip', '.rar', '.jpg', '.png', '.gif')):
                clean_url = parsed_url._replace(fragment="").geturl()
                links.append(clean_url)

    return list(set(links))

# --- Обновленная функция crawl_website ---
async def crawl_website(start_url: str, max_pages: int = 10) -> List[Tuple[str, str]]:
    """
    Рекурсивно обходит веб-сайт, начиная с start_url, до max_pages, используя Playwright
    и имитируя клики по кнопкам категорий для раскрытия контента.
    Возвращает список кортежей (url, content) для всех успешно спарсенных страниц.
    """
    visited_urls = set()
    urls_to_visit = {start_url}
    scraped_data: List[Tuple[str, str]] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
        page = await browser.new_page()
        while urls_to_visit and len(scraped_data) < max_pages:
            current_url = urls_to_visit.pop()
            if current_url in visited_urls:
                continue

            print(f"Обход: {current_url}")
            visited_urls.add(current_url)

            try:
                await page.goto(current_url, wait_until="domcontentloaded", timeout=60000)
                # Удаляем wait_for_load_state("networkidle") здесь, чтобы не конфликтовать с внутренним ожиданием click
                # await page.wait_for_load_state("networkidle")

                interaction_selectors = [
                    'button[data-category-name][data-name="custom-services-category"]',
                    'button:has-text("Каталог")',
                    'a:has-text("Каталог")',
                    'button:has-text("Услуги")',
                    'a:has-text("Услуги")',
                    'button:has-text("Показать")',
                    'a:has-text("Показать")',
                    'button:has-text("Развернуть")',
                    'a:has-text("Развернуть")',
                    'button:has-text("Все услуги")',
                    'a:has-text("Все услуги")',
                ]
                
                elements_to_click_locators = []
                for selector in interaction_selectors:
                    try:
                        found_elements = await page.locator(selector).all()
                        if found_elements:
                            print(f"   Найдены элементы по селектору '{selector}': {len(found_elements)} шт.")
                            elements_to_click_locators.extend(found_elements)
                    except Exception as e:
                        print(f"   Ошибка при поиске по селектору '{selector}': {e}")
                
                unique_elements_info = []
                seen_texts = set()
                
                for el_locator in elements_to_click_locators:
                    try:
                        el_text = (await el_locator.inner_text()).strip()
                        if el_text and el_text not in seen_texts:
                            unique_elements_info.append((el_text, el_locator))
                            seen_texts.add(el_text)
                    except Exception as e:
                        print(f"   Ошибка при получении текста элемента: {e}")


                if unique_elements_info:
                    print(f"   Будет имитирован клик по {len(unique_elements_info)} уникальным потенциальным кнопкам/ссылкам.")
                    max_clicks_per_page = 10 
                    
                    for i, (button_text, button_locator) in enumerate(unique_elements_info):
                        if i >= max_clicks_per_page:
                            print(f"     Достигнут лимит в {max_clicks_per_page} кликов по потенциальным кнопкам на странице. Пропускаем остальные.")
                            break
                        
                        print(f"     Кликаем на: '{button_text}'")
                        try:
                            await button_locator.click(timeout=60000) 
                            # Увеличим таймаут ожидания селектора и сделаем его более общим для списка услуг
                            await page.wait_for_selector('div[class*="Services_servicesItem"]', timeout=30000)
                            await asyncio.sleep(3) # Дополнительная задержка для полной стабилизации и загрузки
                            print(f"     ✅ Клик по '{button_text}' выполнен.")
                        except Exception as click_e:
                            print(f"     ❌ Не удалось кликнуть по '{button_text}' или дождаться стабилизации: {click_e}")
                else:
                    print("   Потенциальные кнопки/ссылки для раскрытия контента не найдены на этой странице.")
                
                html_content = await page.content()
                content = _parse_html_to_text(html_content, url=current_url)

                if content:
                    scraped_data.append((current_url, content))
                    print(f"   ✅ Спарсено ({len(content)} символов). Всего страниц: {len(scraped_data)}")
                else:
                    print(f"   ❌ Не удалось спарсить контент.")

                new_links = await _extract_links(html_content, current_url)
                for link in new_links:
                    if link not in visited_urls and (len(scraped_data) + len(urls_to_visit)) < max_pages:
                        urls_to_visit.add(link)

            except Exception as e:
                print(f"   Произошла ошибка при обходе {current_url}: {e}")
            
        await browser.close()
    print(f"\nОбход завершен. Всего спарсено {len(scraped_data)} страниц.")
    return scraped_data

if __name__ == "__main__":
    async def test_scraper():
        print("Тестирование crawl_website с Playwright и имитацией кликов...")
        crawled_pages = await crawl_website("https://wowvolosy.clients.site/", max_pages=3)
        for url, content in crawled_pages:
            print(f"Crawled: {url} ({len(content)} chars)")
            print(f"Content snippet: {content[:100]}...\n")

    asyncio.run(test_scraper())

