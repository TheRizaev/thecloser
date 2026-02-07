# services/rag_service.py
"""
RAG (Retrieval-Augmented Generation) сервис для работы с базой знаний
Реализует чтение файлов, чанкинг, векторизацию через OpenAI и поиск
"""

import os
import re
import time
import logging
from typing import List, Dict, Optional, Tuple
from io import BytesIO

# Библиотеки для чтения файлов
import pypdf
from docx import Document

# OpenAI для embeddings и генерации
import openai
from openai import OpenAI

# Django imports
from django.conf import settings
from django.db.models import F

# Настройка логирования
logger = logging.getLogger(__name__)


class FileReader:
    """
    Класс для извлечения текста из различных форматов файлов
    """
    
    @staticmethod
    def read_pdf(file_path: str) -> str:
        """
        Читает PDF файл и извлекает текст
        
        Args:
            file_path: Путь к PDF файлу
            
        Returns:
            Извлеченный текст
        """
        try:
            text = ""
            with open(file_path, 'rb') as file:
                pdf_reader = pypdf.PdfReader(file)
                
                for page_num in range(len(pdf_reader.pages)):
                    page = pdf_reader.pages[page_num]
                    text += page.extract_text() + "\n\n"
            
            logger.info(f"PDF файл прочитан: {file_path}, страниц: {len(pdf_reader.pages)}")
            return text
            
        except Exception as e:
            logger.error(f"Ошибка чтения PDF файла {file_path}: {str(e)}")
            raise
    
    @staticmethod
    def read_docx(file_path: str) -> str:
        """
        Читает DOCX файл и извлекает текст
        
        Args:
            file_path: Путь к DOCX файлу
            
        Returns:
            Извлеченный текст
        """
        try:
            doc = Document(file_path)
            text = ""
            
            # Извлекаем текст из параграфов
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            
            # Извлекаем текст из таблиц
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        text += cell.text + " "
                    text += "\n"
            
            logger.info(f"DOCX файл прочитан: {file_path}, параграфов: {len(doc.paragraphs)}")
            return text
            
        except Exception as e:
            logger.error(f"Ошибка чтения DOCX файла {file_path}: {str(e)}")
            raise
    
    @staticmethod
    def read_txt(file_path: str) -> str:
        """
        Читает TXT файл
        
        Args:
            file_path: Путь к TXT файлу
            
        Returns:
            Извлеченный текст
        """
        try:
            # Пробуем разные кодировки
            encodings = ['utf-8', 'windows-1251', 'cp1252', 'iso-8859-1']
            
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as file:
                        text = file.read()
                    logger.info(f"TXT файл прочитан с кодировкой {encoding}: {file_path}")
                    return text
                except UnicodeDecodeError:
                    continue
            
            # Если все кодировки не подошли, читаем как binary и игнорируем ошибки
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
                text = file.read()
            logger.warning(f"TXT файл прочитан с игнорированием ошибок: {file_path}")
            return text
            
        except Exception as e:
            logger.error(f"Ошибка чтения TXT файла {file_path}: {str(e)}")
            raise
    
    @staticmethod
    def read_file(file_path: str) -> str:
        """
        Определяет тип файла и извлекает текст
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            Извлеченный текст
        """
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext == '.pdf':
            return FileReader.read_pdf(file_path)
        elif ext == '.docx':
            return FileReader.read_docx(file_path)
        elif ext == '.txt':
            return FileReader.read_txt(file_path)
        else:
            raise ValueError(f"Неподдерживаемый формат файла: {ext}")


class TextCleaner:
    """
    Класс для очистки текста от лишних символов и форматирования
    """
    
    @staticmethod
    def clean_text(text: str) -> str:
        """
        Очищает текст от лишних пробелов, переносов и мусора
        
        Args:
            text: Исходный текст
            
        Returns:
            Очищенный текст
        """
        # Удаляем множественные пробелы
        text = re.sub(r'\s+', ' ', text)
        
        # Удаляем множественные переносы строк
        text = re.sub(r'\n\s*\n', '\n\n', text)
        
        # Удаляем пробелы в начале и конце строк
        text = '\n'.join(line.strip() for line in text.split('\n'))
        
        # Удаляем специальные символы (но оставляем знаки препинания)
        text = re.sub(r'[^\w\s\.\,\!\?\-\:\;\(\)\"\'\n]', '', text, flags=re.UNICODE)
        
        # Убираем пробелы в начале и конце всего текста
        text = text.strip()
        
        return text


class TextChunker:
    """
    Класс для разбиения текста на смысловые чанки
    """
    
    def __init__(self, chunk_size: int = 1000, overlap: int = 200):
        """
        Args:
            chunk_size: Размер чанка в символах
            overlap: Размер перекрытия между чанками в символах
        """
        self.chunk_size = chunk_size
        self.overlap = overlap
    
    def split_text(self, text: str) -> List[str]:
        """
        Разбивает текст на чанки с перекрытием
        
        Args:
            text: Исходный текст
            
        Returns:
            Список чанков
        """
        # Очищаем текст
        text = TextCleaner.clean_text(text)
        
        # Если текст короче чем chunk_size, возвращаем как есть
        if len(text) <= self.chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            # Определяем конец чанка
            end = start + self.chunk_size
            
            # Если это не последний чанк, пытаемся найти конец предложения
            if end < len(text):
                # Ищем точку, восклицательный или вопросительный знак
                sentence_end = max(
                    text.rfind('.', start, end),
                    text.rfind('!', start, end),
                    text.rfind('?', start, end)
                )
                
                # Если нашли конец предложения, используем его
                if sentence_end > start:
                    end = sentence_end + 1
            
            # Добавляем чанк
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            # Сдвигаемся с учетом перекрытия
            start = end - self.overlap
            
            # Защита от бесконечного цикла
            if start <= 0:
                start = end
        
        logger.info(f"Текст разбит на {len(chunks)} чанков")
        return chunks


class OpenAIEmbedder:
    """
    Класс для получения embeddings через OpenAI API
    """
    
    def __init__(self, api_key: Optional[str] = None, model: str = "text-embedding-3-small"):
        """
        Args:
            api_key: OpenAI API ключ (если None, берется из settings)
            model: Модель для embeddings
        """
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = model
        self.client = OpenAI(api_key=self.api_key)
        
        # Параметры для retry
        self.max_retries = 3
        self.retry_delay = 1  # секунды
    
    def get_embedding(self, text: str, retry_count: int = 0) -> List[float]:
        """
        Получает embedding для текста с поддержкой retry
        
        Args:
            text: Текст для векторизации
            retry_count: Текущая попытка (для рекурсии)
            
        Returns:
            Вектор embedding
        """
        try:
            response = self.client.embeddings.create(
                input=text,
                model=self.model
            )
            
            embedding = response.data[0].embedding
            logger.debug(f"Получен embedding, размер: {len(embedding)}")
            return embedding
            
        except openai.RateLimitError as e:
            if retry_count < self.max_retries:
                wait_time = self.retry_delay * (2 ** retry_count)  # Exponential backoff
                logger.warning(f"Rate limit, ожидание {wait_time} секунд...")
                time.sleep(wait_time)
                return self.get_embedding(text, retry_count + 1)
            else:
                logger.error(f"Превышен лимит попыток для получения embedding")
                raise
                
        except openai.APIError as e:
            if retry_count < self.max_retries:
                wait_time = self.retry_delay * (2 ** retry_count)
                logger.warning(f"API ошибка, повтор через {wait_time} секунд...")
                time.sleep(wait_time)
                return self.get_embedding(text, retry_count + 1)
            else:
                logger.error(f"API ошибка после {self.max_retries} попыток: {str(e)}")
                raise
                
        except Exception as e:
            logger.error(f"Неожиданная ошибка при получении embedding: {str(e)}")
            raise
    
    def get_embeddings_batch(self, texts: List[str], batch_size: int = 100) -> List[List[float]]:
        """
        Получает embeddings для списка текстов с батчингом
        
        Args:
            texts: Список текстов
            batch_size: Размер батча
            
        Returns:
            Список векторов
        """
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            logger.info(f"Обработка батча {i//batch_size + 1}, текстов: {len(batch)}")
            
            for text in batch:
                embedding = self.get_embedding(text)
                all_embeddings.append(embedding)
            
            # Небольшая задержка между батчами
            if i + batch_size < len(texts):
                time.sleep(0.5)
        
        logger.info(f"Получены embeddings для {len(all_embeddings)} текстов")
        return all_embeddings


class RAGService:
    """
    Основной класс RAG-сервиса
    """
    
    def __init__(self):
        self.file_reader = FileReader()
        self.text_chunker = TextChunker(chunk_size=1200, overlap=200)
        self.embedder = OpenAIEmbedder()
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
    
    def process_document(self, knowledge_base_id: int, file_path: str) -> int:
        """
        Обрабатывает документ: читает, разбивает на чанки, векторизует и сохраняет
        
        Args:
            knowledge_base_id: ID записи KnowledgeBase
            file_path: Путь к файлу
            
        Returns:
            Количество созданных чанков
        """
        from core.models import KnowledgeBase, KnowledgeChunk
        
        try:
            # Получаем объект KnowledgeBase
            kb = KnowledgeBase.objects.get(id=knowledge_base_id)
            
            # Читаем файл
            logger.info(f"Чтение файла: {file_path}")
            text = self.file_reader.read_file(file_path)
            
            # Разбиваем на чанки
            logger.info("Разбиение на чанки...")
            chunks = self.text_chunker.split_text(text)
            
            # Удаляем старые чанки для этого документа (если есть)
            KnowledgeChunk.objects.filter(knowledge_base=kb).delete()
            
            # Обрабатываем каждый чанк
            logger.info(f"Векторизация {len(chunks)} чанков...")
            for idx, chunk_text in enumerate(chunks):
                # Получаем embedding
                embedding = self.embedder.get_embedding(chunk_text)
                
                # Сохраняем в БД
                KnowledgeChunk.objects.create(
                    knowledge_base=kb,
                    text=chunk_text,
                    embedding=embedding,
                    chunk_index=idx
                )
                
                if (idx + 1) % 10 == 0:
                    logger.info(f"Обработано {idx + 1}/{len(chunks)} чанков")
            
            # Обновляем статус в KnowledgeBase
            kb.is_indexed = True
            kb.save()
            
            logger.info(f"Документ успешно обработан, создано {len(chunks)} чанков")
            return len(chunks)
            
        except Exception as e:
            logger.error(f"Ошибка обработки документа: {str(e)}")
            # Помечаем документ как проблемный
            try:
                kb = KnowledgeBase.objects.get(id=knowledge_base_id)
                kb.is_indexed = False
                kb.save()
            except:
                pass
            raise
    
    def search_knowledge_base(self, bot_id: int, query: str, top_k: int = 5) -> List[Dict]:
        """
        Ищет релевантные чанки в базе знаний для указанного бота
        
        Args:
            bot_id: ID бота
            query: Поисковый запрос
            top_k: Количество результатов
            
        Returns:
            Список релевантных чанков с метаданными
        """
        from core.models import KnowledgeChunk
        
        try:
            # Получаем embedding для запроса
            logger.info(f"Поиск в базе знаний для бота {bot_id}: {query[:100]}...")
            query_embedding = self.embedder.get_embedding(query)
            
            # Используем pgvector для поиска ближайших векторов
            # Примечание: требуется установленный pgvector и настроенная БД
            from django.contrib.postgres.search import SearchVector
            from pgvector.django import CosineDistance
            
            results = KnowledgeChunk.objects.filter(
                knowledge_base__bot__id=bot_id,
                knowledge_base__is_indexed=True
            ).annotate(
                distance=CosineDistance('embedding', query_embedding)
            ).order_by('distance')[:top_k]
            
            # Формируем результаты
            formatted_results = []
            for result in results:
                formatted_results.append({
                    'text': result.text,
                    'distance': float(result.distance),
                    'source': result.knowledge_base.file.name,
                    'chunk_index': result.chunk_index
                })
            
            logger.info(f"Найдено {len(formatted_results)} релевантных чанков")
            return formatted_results
            
        except Exception as e:
            logger.error(f"Ошибка поиска в базе знаний: {str(e)}")
            # Возвращаем пустой список в случае ошибки
            return []
    
    def generate_answer(
        self, 
        query: str, 
        context_chunks: List[Dict],
        model: str = "gpt-4o-mini",
        max_tokens: int = 500
    ) -> str:
        """
        Генерирует ответ на основе найденных чанков
        
        Args:
            query: Вопрос пользователя
            context_chunks: Список релевантных чанков
            model: Модель GPT для генерации
            max_tokens: Максимальное количество токенов в ответе
            
        Returns:
            Сгенерированный ответ
        """
        try:
            # Формируем контекст из чанков
            context = "\n\n".join([
                f"[Источник: {chunk['source']}, часть {chunk['chunk_index'] + 1}]\n{chunk['text']}"
                for chunk in context_chunks
            ])
            
            # Формируем промпт
            system_prompt = """Ты — ассистент, который отвечает на вопросы СТРОГО на основе предоставленного контекста.

ВАЖНЫЕ ПРАВИЛА:
1. Используй ТОЛЬКО информацию из предоставленного контекста
2. Если ответа нет в контексте, честно скажи "В предоставленных документах нет информации по этому вопросу"
3. Не добавляй свои знания или домыслы
4. Отвечай четко и по существу
5. Указывай источник информации, если это уместно"""
            
            user_prompt = f"""Контекст из базы знаний:
{context}

Вопрос пользователя: {query}

Ответь на вопрос на основе предоставленного контекста:"""
            
            # Генерируем ответ
            logger.info("Генерация ответа через GPT...")
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=max_tokens,
                temperature=0.3  # Низкая температура для более точных ответов
            )
            
            answer = response.choices[0].message.content
            logger.info("Ответ успешно сгенерирован")
            return answer
            
        except Exception as e:
            logger.error(f"Ошибка генерации ответа: {str(e)}")
            return "Извините, произошла ошибка при генерации ответа. Пожалуйста, попробуйте позже."
    
    def answer_question(self, bot_id: int, query: str, top_k: int = 5) -> Dict:
        """
        Полный цикл: поиск + генерация ответа
        
        Args:
            bot_id: ID бота
            query: Вопрос пользователя
            top_k: Количество чанков для поиска
            
        Returns:
            Словарь с ответом и метаданными
        """
        try:
            # Ищем релевантные чанки
            context_chunks = self.search_knowledge_base(bot_id, query, top_k)
            
            # Если ничего не найдено
            if not context_chunks:
                return {
                    'answer': "К сожалению, я не нашел информации по вашему вопросу в базе знаний.",
                    'sources': [],
                    'confidence': 0.0
                }
            
            # Генерируем ответ
            answer = self.generate_answer(query, context_chunks)
            
            # Формируем метаданные
            sources = list(set([chunk['source'] for chunk in context_chunks]))
            avg_distance = sum(chunk['distance'] for chunk in context_chunks) / len(context_chunks)
            confidence = 1.0 - avg_distance  # Конвертируем distance в confidence
            
            return {
                'answer': answer,
                'sources': sources,
                'confidence': round(confidence, 2),
                'chunks_used': len(context_chunks)
            }
            
        except Exception as e:
            logger.error(f"Ошибка в answer_question: {str(e)}")
            return {
                'answer': "Произошла ошибка при обработке запроса.",
                'sources': [],
                'confidence': 0.0,
                'error': str(e)
            }


rag_service = RAGService()