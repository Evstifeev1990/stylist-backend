import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    print("Ошибка: GOOGLE_API_KEY не найден в .env файле!")
else:
    genai.configure(api_key=api_key)
    print("Доступные модели для эмбеддингов:")
    try:
        for m in genai.list_models():
            if 'embedContent' in m.supported_generation_methods:
                print(f"- {m.name}")
    except Exception as e:
        print(f"Ошибка при получении списка моделей: {e}")