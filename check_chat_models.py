import os
from dotenv import load_dotenv
import google.generativeai as genai

# Загружаем переменные окружения из .env
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    print("Ошибка: GOOGLE_API_KEY не найден в .env файле!")
else:
    genai.configure(api_key=api_key)
    print("Доступные модели для чата (LLM) через genai.list_models():")
    try:
        found_chat_models = []
        for m in genai.list_models():
            # Проверяем, поддерживает ли модель метод 'generateContent' (для чата)
            if 'generateContent' in m.supported_generation_methods:
                found_chat_models.append(m.name)
                print(f"- {m.name}")
        
        if not found_chat_models:
            print("Не найдено доступных моделей для чата с вашим ключом.")

    except Exception as e:
        print(f"Ошибка при получении списка моделей: {e}")