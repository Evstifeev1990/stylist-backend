# src/rag/embeddings_and_vector_db.py
import os
import time  # Импортируем time для time.sleep
from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from typing import List
from tenacity import retry, wait_random_exponential, stop_after_attempt

# Загружаем переменные окружения из .env
load_dotenv()

# Константы для батчинга эмбеддингов
EMBEDDING_BATCH_SIZE = 50  # Количество документов для отправки в API за один раз
EMBEDDING_DELAY_SECONDS = 40 # Задержка в секундах между партиями для соблюдения квоты

@retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(5), reraise=True)
def create_vector_db(documents: List[Document], collection_name: str = "website_data"):
    """
    Превращает объекты Document в эмбеддинги и сохраняет их в ChromaDB партиями,
    соблюдая ограничения квоты Google Embeddings API.
    """
    persist_directory = "./chroma_db"
    
    # Инициализируем модель эмбеддингов от Google один раз
    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-2-preview")

    # Удаляем существующую базу данных, чтобы пересоздать её с нуля при индексации
    # Это важно, так как мы полностью переиндексируем сайт
    if os.path.exists(persist_directory):
        import shutil
        shutil.rmtree(persist_directory)
        print(f"Удалена существующая база данных: {persist_directory}")
    
    # Создаем новую, пока пустую, коллекцию Chroma
    vector_db = Chroma(
        embedding_function=embeddings,
        persist_directory=persist_directory,
        collection_name=collection_name
    )

    print(f"Начинаем создание векторной базы данных. Всего чанков: {len(documents)}")

    # Разделяем документы на партии и добавляем их по очереди
    for i in range(0, len(documents), EMBEDDING_BATCH_SIZE):
        batch = documents[i:i + EMBEDDING_BATCH_SIZE]
        print(f"  Обрабатываем партию документов: с {i+1} по {min(i + EMBEDDING_BATCH_SIZE, len(documents))} из {len(documents)}")
        try:
            vector_db.add_documents(documents=batch)
            print(f"  ✅ Партия успешно добавлена.")
        except Exception as e:
            if "RESOURCE_EXHAUSTED" in str(e):
                print(f"  ВНИМАНИЕ: Превышена квота Google Embeddings API для текущей партии. Повторная попытка через некоторое время...")
            # Перевыбрасываем исключение, чтобы декоратор @retry мог его перехватить
            raise e 
        
        # Если это не последняя партия, делаем задержку
        if i + EMBEDDING_BATCH_SIZE < len(documents):
            print(f"  Ожидаем {EMBEDDING_DELAY_SECONDS} секунд перед следующей партией для соблюдения квоты API...")
            time.sleep(EMBEDDING_DELAY_SECONDS)
        
    print(f"База данных успешно создана и сохранена в {persist_directory}")
    return vector_db
        
@retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(3), reraise=True)
def query_vector_db(query: str, collection_name: str = "website_data"):
    """
    Ищет наиболее похожие куски текста в базе данных по запросу.
    Автоматически повторяет попытку при ошибках квоты (429).
    """
    try:
        embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-2-preview")
        persist_directory = "./chroma_db"
        
        # Загружаем существующую базу
        vector_db = Chroma(
            persist_directory=persist_directory,
            embedding_function=embeddings,
            collection_name=collection_name
        )
        
        # Ищем 3 самых релевантных документа
        results = vector_db.similarity_search(query, k=3)
        return results
    except Exception as e:
        if "RESOURCE_EXHAUSTED" in str(e):
            print(f"ВНИМАНИЕ: Превышена квота Google Embeddings API при поиске. Ожидаем и повторяем попытку...")
        raise e

if __name__ == "__main__":
    # Тестовый запуск - теперь передаем Document объекты
    test_chunks_data = [
        "Python — это язык программирования, который позволяет работать быстро.",
        "Векторные базы данных хранят информацию в виде чисел.",
        "Gemini — это модель искусственного интеллекта от Google.",
        "Завтра в Москве будет солнечная погода."
    ]
    # Преобразуем строки в Document объекты для теста
    test_documents = [Document(page_content=text, metadata={"source": "test_data"}) for text in test_chunks_data]
    
    print("Создаем базу данных...")
    create_vector_db(test_documents)
    
    print("\nПроверяем поиск...\n")
    question = "Расскажи про нейросети от Гугла"
    search_results = query_vector_db(question)
    
    for i, doc in enumerate(search_results):
        print(f"Результат {i+1}: {doc.page_content} (Source: {doc.metadata.get('source', 'N/A')})")

