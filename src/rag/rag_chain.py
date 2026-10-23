# src/rag/rag_chain.py
import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

# Загружаем ключи
load_dotenv()

def get_rag_chain():
    """
    Создает и возвращает RAG-цепочку.
    """
    # 1. Настраиваем модель эмбеддингов (ту, что заработала!)
    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-2-preview")
    
    # 2. Подключаемся к существующей базе данных
    vector_db = Chroma(
        persist_directory="./chroma_db",
        embedding_function=embeddings,
        collection_name="website_data"
    )
    
    # 3. Настраиваем ретривер (поисковик по базе)
    # search_kwargs={"k": 10} - Увеличиваем количество извлекаемых чанков
    retriever = vector_db.as_retriever(search_kwargs={"k": 10}) 
    # temperature=0 делает ответы более точными и менее "творческими"
    llm = ChatGoogleGenerativeAI(model="models/gemini-2.5-flash", temperature=0)
    
    # 5. Создаем шаблон промпта
    template = """Ты — полезный ассиент службы поддержки, специализирующийся на предоставлении информации об услугах.
    Используй предоставленный контекст, чтобы ответить на вопрос. 
    Если вопрос касается списка услуг или каталога, постарайся вывести названия услуг списком.
    Если в контексте нет ответа, честно скажи, что ты не знаешь. 
    Не выдумывай информацию.

    КОНТЕКСТ:
    {context}

    ВОПРОС: 
    {question}

    ОТВЕТ:"""
    
    prompt = ChatPromptTemplate.from_template(template)
    
    # 6. Собираем цепочку (Chain)
    # Это "конвейер": данные текут от ретривера к промпту, затем в LLM и парсер
    rag_chain = (
        {"context": retriever, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )
    
    return rag_chain

if __name__ == "__main__":
    # Тестовый запрос к нашей базе (в которой сейчас данные про Python и Gemini)
    chain = get_rag_chain()
    
    question = "Что такое душа"
    print(f"Вопрос: {question}")
    
    response = chain.invoke(question)
    print("\nОтвет ассистента:")
    print(response)
