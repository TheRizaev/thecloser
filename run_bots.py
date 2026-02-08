#!/usr/bin/env python
"""
The Closer Worker - ИСПРАВЛЕННАЯ ВЕРСИЯ
Исправления:
1. RAG фильтр через ManyToMany (knowledge_base__bots__id)
2. Удалена функция increment_bot_stats (поле total_messages не существует)
"""
import asyncio
import os
import sys
import django
import logging
import random
from asgiref.sync import sync_to_async

# ===== Django Setup =====
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.utils import timezone
from core.models import BotAgent, Conversation, Message as MessageModel

# ===== RAG Service Import =====
from services.rag_service import rag_service

# ===== Telethon & OpenAI =====
from telethon import TelegramClient, events, functions
from telethon.sessions import StringSession

try:
    from openai import OpenAI, OpenAIError
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("⚠️ Библиотека openai не установлена")

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("BotWorker")

# OpenAI
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
ai_client = None

if OPENAI_AVAILABLE and OPENAI_API_KEY:
    try:
        ai_client = OpenAI(api_key=OPENAI_API_KEY)
        logger.info("✅ OpenAI client initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize OpenAI: {e}")
elif not OPENAI_API_KEY:
    logger.warning("⚠️ OPENAI_API_KEY не найден в .env")

active_clients = {}


# ==========================================
# 1. Database Async Wrappers
# ==========================================

@sync_to_async
def get_active_bots_from_db():
    """Получает активных ботов"""
    return list(BotAgent.objects.filter(
        platform='telegram',
        status='active'
    ).exclude(session_string='').exclude(session_string__isnull=True))

@sync_to_async
def get_bot_by_id(bot_id):
    """Получает бота по ID"""
    try:
        return BotAgent.objects.get(id=bot_id)
    except BotAgent.DoesNotExist:
        return None

@sync_to_async
def get_or_create_conversation(bot_instance, user_id, user_name):
    """Создает/получает диалог"""
    conversation, created = Conversation.objects.get_or_create(
        bot=bot_instance,
        user_id=user_id,
        defaults={
            'user_name': user_name,
            'started_at': timezone.now()
        }
    )
    conversation.last_message_at = timezone.now()
    conversation.save(update_fields=['last_message_at'])
    return conversation

@sync_to_async
def save_message_to_db(conversation, role, content):
    """Сохраняет сообщение"""
    return MessageModel.objects.create(
        conversation=conversation,
        role=role,
        content=content
    )

@sync_to_async
def mark_bot_invalid(bot_id):
    """Помечает бота как invalid"""
    BotAgent.objects.filter(id=bot_id).update(status='error')


# ==========================================
# 2. RAG Integration
# ==========================================

@sync_to_async
def get_rag_response(bot_id, query):
    """Получает ответ через RAG"""
    try:
        result = rag_service.answer_question(bot_id, query, top_k=5)
        return result
    except Exception as e:
        logger.error(f"RAG Error for bot {bot_id}: {e}")
        return {
            'answer': None,
            'sources': [],
            'confidence': 0.0
        }


# ==========================================
# 3. AI Logic with RAG
# ==========================================

async def get_chatgpt_response(message_text, system_prompt, bot_id=None, use_rag=False):
    """Запрос к OpenAI с RAG поддержкой"""
    if not ai_client:
        return "⚠️ Ошибка: AI клиент не инициализирован."

    try:
        # RAG поиск
        rag_context = ""
        rag_sources = []
        
        if use_rag and bot_id:
            logger.info(f"🔍 [Bot {bot_id}] Searching knowledge base...")
            rag_result = await get_rag_response(bot_id, message_text)
            
            if rag_result and rag_result.get('answer'):
                rag_context = f"\n\n📚 ИНФОРМАЦИЯ ИЗ БАЗЫ ЗНАНИЙ:\n{rag_result['answer']}\n"
                rag_sources = rag_result.get('sources', [])
                logger.info(f"✅ [Bot {bot_id}] RAG found info (confidence: {rag_result.get('confidence', 0):.2f})")
            else:
                logger.info(f"ℹ️ [Bot {bot_id}] No relevant info in knowledge base")
        
        # Формируем промпт
        enhanced_prompt = system_prompt
        
        if rag_context:
            enhanced_prompt += """

ВАЖНО: Используй информацию из базы знаний для ответа.
Отвечай естественно, как живой человек.
"""
            enhanced_prompt += rag_context
        
        # Запрос к OpenAI
        loop = asyncio.get_event_loop()
        
        response = await loop.run_in_executor(
            None,
            lambda: ai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": enhanced_prompt},
                    {"role": "user", "content": message_text}
                ],
                temperature=0.7,
                max_tokens=1000
            )
        )
        
        answer = response.choices[0].message.content.strip()
        
        return answer
        
    except Exception as e:
        logger.error(f"OpenAI Error: {e}")
        return "Извините, я сейчас не могу ответить. Попробуйте позже."


# ==========================================
# 4. Bot Behavior
# ==========================================

async def keep_online_loop(client, bot_name):
    """Держит статус 'Online'"""
    while True:
        try:
            await client(functions.account.UpdateStatusRequest(offline=False))
        except Exception as e:
            logger.error(f"[{bot_name}] Failed to update status: {e}")
        
        await asyncio.sleep(300 + random.randint(0, 10))


async def handle_message(event, bot_id):
    """Обработчик сообщений с RAG"""
    
    bot_record = await get_bot_by_id(bot_id)
    if not bot_record or bot_record.status != 'active':
        return

    sender = await event.get_sender()
    user_id = str(sender.id)
    user_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip() or "Unknown"
    text = event.message.text

    if not text:
        return

    logger.info(f"📨 [{bot_record.name}] New msg from {user_name}: {text[:50]}...")

    # Сохраняем входящее
    conversation = await get_or_create_conversation(bot_record, user_id, user_name)
    await save_message_to_db(conversation, 'user', text)

    # --- ЭМУЛЯЦИЯ ЧЕЛОВЕКА ---
    
    # 1. Задержка чтения
    read_delay = 5 + random.randint(0, 5)
    await asyncio.sleep(read_delay)

    # 2. Прочитано
    try:
        await event.message.mark_read()
    except:
        pass
    
    # 3. Генерация ответа с RAG
    system_prompt = bot_record.system_prompt or "Ты полезный ассистент."
    use_rag = bot_record.use_rag
    
    response_text = await get_chatgpt_response(
        text, 
        system_prompt,
        bot_id=bot_id,
        use_rag=use_rag
    )

    # 4. Печать
    typing_speed = random.randint(5, 8)
    typing_duration = len(response_text) / typing_speed
    typing_duration = max(2.0, min(15.0, typing_duration))

    # 5. Статус "Печатает..."
    try:
        async with event.client.action(event.chat_id, 'typing'):
            await asyncio.sleep(typing_duration)
    except:
        await asyncio.sleep(typing_duration)

    # 6. Отправка
    await event.reply(response_text)
    
    # 7. Сохранение
    await save_message_to_db(conversation, 'bot', response_text)
    
    # ========== ИСПРАВЛЕНИЕ: Удалена функция increment_bot_stats ==========
    # Статистика теперь считается через количество Message объектов
    
    logger.info(f"✅ [{bot_record.name}] Replied to {user_name} (RAG: {use_rag})")


# ==========================================
# 5. Process Management
# ==========================================

async def start_single_bot(bot_record):
    """Запуск одного бота"""
    try:
        api_id = int(bot_record.api_id)
        api_hash = bot_record.api_hash
        session_str = bot_record.session_string

        client = TelegramClient(StringSession(session_str), api_id, api_hash)
        
        await client.connect()
        
        if not await client.is_user_authorized():
            logger.error(f"❌ Bot [{bot_record.name}] session invalid")
            await mark_bot_invalid(bot_record.id)
            return

        @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
        async def wrapper(event, b_id=bot_record.id):
            await handle_message(event, b_id)

        online_task = asyncio.create_task(keep_online_loop(client, bot_record.name))
        
        active_clients[bot_record.id] = {
            'client': client,
            'tasks': [online_task]
        }
        
        me = await client.get_me()
        rag_status = "✅ RAG ON" if bot_record.use_rag else "❌ RAG OFF"
        logger.info(f"🚀 Bot started: {bot_record.name} (@{me.username}) | {rag_status}")

    except Exception as e:
        logger.error(f"❌ Error starting bot {bot_record.name}: {e}")


async def stop_single_bot(bot_id):
    """Остановка бота"""
    if bot_id in active_clients:
        data = active_clients[bot_id]
        
        for task in data.get('tasks', []):
            task.cancel()
        
        client = data['client']
        await client.disconnect()
        
        del active_clients[bot_id]
        logger.info(f"🛑 Bot ID {bot_id} stopped")


async def monitor_manager():
    """Мониторинг ботов"""
    logger.info("👀 Monitor Manager started...")
    logger.info(f"📚 RAG Service: {'✅ Available' if rag_service else '❌ Not available'}")
    
    while True:
        try:
            db_bots = await get_active_bots_from_db()
            db_bot_ids = set(b.id for b in db_bots)
            running_ids = set(active_clients.keys())

            # Запуск новых
            for bot_id in (db_bot_ids - running_ids):
                bot_obj = next(b for b in db_bots if b.id == bot_id)
                asyncio.create_task(start_single_bot(bot_obj))

            # Остановка старых
            for bot_id in (running_ids - db_bot_ids):
                asyncio.create_task(stop_single_bot(bot_id))

        except Exception as e:
            logger.error(f"Monitor error: {e}")
        
        await asyncio.sleep(10)


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(monitor_manager())
    except KeyboardInterrupt:
        logger.info("👋 Shutting down...")
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))