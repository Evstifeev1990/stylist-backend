from langchain_text_splitters import RecursiveCharacterTextSplitter
from typing import List

def split_text_into_chunks(text: str, chunk_size: int = 600, chunk_overlap: int = 100) -> List[str]:
    """
    Разбивает длинный текст на небольшие чанки.
    
    chunk_size: Максимальный размер чанка (в символах).
    chunk_overlap: Перекрытие между чанками (чтобы не потерять смысл на стыке).
    """
    # Инициализируем разделитель
    # Он сначала пытается делить по \n\n (абзацы), затем по \n (строки), затем по пробелам.
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", " ", ""]
    )
    
    # Создаем чанки (просто как список строк)
    chunks = text_splitter.split_text(text)
    return chunks

if __name__ == "__main__":
    # Тестовый пример
    test_text = "Это очень длинный текст. " * 50  # Создаем искусственно длинную строку
    
    print(f"Длина исходного текста: {len(test_text)} символов.")
    
    chunks = split_text_into_chunks(test_text, chunk_size=100, chunk_overlap=20)
    
    print(f"Количество созданных чанков: {len(chunks)}")
    print(f"Первый чанк: {chunks[0]}")
    print(f"Второй чанк: {chunks[1]}")