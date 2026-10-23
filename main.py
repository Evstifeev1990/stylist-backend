import asyncio
import sys
from typing import List, Optional, Tuple
from langchain_core.documents import Document

# Импортируем функции из наших модулей
from src.rag.scraper import crawl_website
from src.rag.text_processing import split_text_into_chunks
from src.rag.embeddings_and_vector_db import create_vector_db
from src.rag.rag_chain import get_rag_chain

async def index_website(start_urls: List[str], max_crawl_pages: int = 10):
    """
    Парсит один или несколько стартовых URL (и обходит их), обрабатывает текст, создает чанки
    и сохраняет их в векторную базу данных.
    """
    all_scraped_pages: List[Tuple[str, str]] = []

    print("Начинаем обход сайтов...")
    crawl_tasks = [crawl_website(start_url, max_pages=max_crawl_pages) for start_url in start_urls]
    crawled_results = await asyncio.gather(*crawl_tasks)

    for result_list in crawled_results:
        all_scraped_pages.extend(result_list)

    if not all_scraped_pages:
        print("Нет данных для индексации. Выход.")
        return

    all_raw_text_documents: List[Document] = []
    for url, content in all_scraped_pages:
        all_raw_text_documents.append(Document(page_content=content, metadata={"source": url}))
    
    print(f"Всего спарсено уникальных страниц: {len(all_raw_text_documents)}")

    print("\nРазбиваем текст на чанки...")
    all_chunks_documents: List[Document] = []
    for doc in all_raw_text_documents:
        chunks_text = split_text_into_chunks(doc.page_content)
        for chunk_text in chunks_text:
            all_chunks_documents.append(Document(page_content=chunk_text, metadata=doc.metadata))

    print(f"Создано {len(all_chunks_documents)} текстовых чанков.")
    
    print("\nСоздаем/обновляем векторную базу данных...")
    print(f"DEBUG: Вызываем create_vector_db с {len(all_chunks_documents)} документами.") # <-- ДОБАВЛЕНО
    create_vector_db(all_chunks_documents)
    
    print("\nИндексация завершена!")

async def main():
    """
    Основная функция для запуска агента из командной строки.
    Обрабатывает команды 'index' и 'chat'.
    """
    if len(sys.argv) < 2:
        print("Использование: python main.py [команда] [аргументы]")
        print("Команды:")
        print("  index <url1> [<url2> ...] [--max-pages <N>] - Индексировать один или несколько URL, обходя до N страниц на каждый.")
        print("  chat \"<ваш вопрос>\"      - Задать вопрос к проиндексированным данным.")
        return

    command = sys.argv[1]

    if command == "index":
        urls_to_index = []
        max_pages = 10
        
        i = 2
        while i < len(sys.argv):
            arg = sys.argv[i]
            if arg == "--max-pages":
                if i + 1 < len(sys.argv):
                    try:
                        max_pages = int(sys.argv[i+1])
                        i += 2
                    except ValueError:
                        print("Ошибка: --max-pages требует числового значения.")
                        return
                else:
                    print("Ошибка: После --max-pages ожидается числовое значение.")
                    return
            else:
                urls_to_index.append(arg)
                i += 1
        
        if not urls_to_index:
            print("Пожалуйста, укажите хотя бы один стартовый URL для индексации.")
            return
            
        print(f"Начинаем индексацию для {len(urls_to_index)} стартовых URL, с обходом до {max_pages} страниц каждый.")
        await index_website(urls_to_index, max_crawl_pages=max_pages)
    elif command == "chat":
        if len(sys.argv) < 3:
            print("Пожалуйста, задайте вопрос.")
            return
        question = " ".join(sys.argv[2:]) 
        
        print(f"Загружаю RAG-цепочку и отвечаю на вопрос: \"{question}\"")
        rag_chain = get_rag_chain()
        
        response = rag_chain.invoke(question)
        print("\nОтвет ассистента:")
        print(response)
    else:
        print(f"Неизвестная команда: {command}")
        print("Доступные команды: index, chat")

if __name__ == "__main__":
    asyncio.run(main())