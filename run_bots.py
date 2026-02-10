#!/usr/bin/env python
"""
The Closer Worker - ФИНАЛЬНАЯ ВЕРСИЯ С "ЧЕЛОВЕЧНОСТЬЮ"
Изменения:
1. Динамическая модель из bot.openai_model
2. HUMANIZER_INSTRUCTIONS с подстановкой {bot_name} и {company_name}
3. Финальный промпт = HUMANIZER + USER_PROMPT + RAG_CONTEXT
"""
import asyncio
import os
import sys
import django
import logging
import random
from asgiref.sync import sync_to_async

import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")

def start_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHandler)
    print(f"🌍 Dummy server listening on port {port}")
    server.serve_forever()

threading.Thread(target=start_dummy_server, daemon=True).start()

# ===== Django Setup =====
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.utils import timezone
from core.models import BotAgent, Conversation, Message as MessageModel
from services.rag_service import rag_service

from telethon import TelegramClient, events, functions
from telethon.sessions import StringSession

try:
    from openai import OpenAI, OpenAIError
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("⚠️ Библиотека openai не установлена")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("BotWorker")

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
# HUMANIZER INSTRUCTIONS (Шаблон)
# ==========================================

HUMANIZER_INSTRUCTIONS_TEMPLATE = """
Ты — {bot_name}.
ТВОЯ РОЛЬ: Опытный сотрудник компании {company_name}. Ты общаешься в Telegram.
ТВОЯ ЦЕЛЬ: Быстро и четко решить вопрос клиента или закрыть сделку.

ПРАВИЛА "АНТИ-РОБОТ" (СТРОГОЕ СОБЛЮДЕНИЕ):
1. **ФОРМАТ СООБЩЕНИЙ:**
   - Пиши короткими предложениями. Люди в чатах не пишут абзацами.
   - Избегай маркированных списков с жирными заголовками, если это не длинная инструкция.
   - Иногда пиши с маленькой буквы (особенно короткие ответы: "ок", "хорошо", "сейчас гляну").
   - Не ставь точку в конце одиночных предложений или коротких фраз.

2. **СТИЛЬ ОБЩЕНИЯ:**
   - **Запрещенные фразы:** "Я языковая модель", "Как искусственный интеллект", "Чем могу быть полезен?", "Обращайтесь, если будут вопросы". За использование — штраф.
   - Не используй сложные вводные конструкции ("Стоит отметить, что..."). Пиши проще: "Кстати...", "Еще момент...".
   - Если не знаешь ответа — не извиняйся расплывчато. Скажи честно: "Так, секунду, уточню этот момент" или "Не уверен, сейчас проверю".
   - Не зеркаль вопрос пользователя (User: "Цена?" -> Bot: "Цена составляет..."). Отвечай сразу сутью ("5000").

3. **ЭМОЦИОНАЛЬНЫЙ ИНТЕЛЛЕКТ:**
   - Не будь "лакеем". Будь профессиональным, но на равных.
   - Если пользователь пишет "Привет", отвечай "Привет" или "Добрый день". Не спрашивай сразу "Чем помочь?". Жди суть.
   - Эмодзи используй редко и к месту.

ТВОЙ ВНУТРЕННИЙ ГОЛОС: Ты занятой человек, который пишет с телефона. Ты вежлив, но краток.
"""


# ==========================================
# Database Async Wrappers
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

@sync_to_async
def get_conversation_history(conversation_id, limit=10):
    """Получает последние сообщения для контекста"""
    messages = MessageModel.objects.filter(conversation_id=conversation_id).order_by('-created_at')[:limit]
    history_objs = list(reversed(messages))
    
    formatted_history = []
    for msg in history_objs:
        role = 'assistant' if msg.role == 'bot' else 'user'
        formatted_history.append({'role': role, 'content': msg.content})
        
    return formatted_history


# ==========================================
# RAG Integration
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
# AI Logic with HUMANIZER + RAG
# ==========================================

async def get_chatgpt_response(message_text, bot_record, history=None):
    """
    Запрос к OpenAI с:
    1. HUMANIZER_INSTRUCTIONS (с подстановкой переменных)
    2. USER_DEFINED_PROMPT (bot.system_prompt)
    3. RAG_CONTEXT (если use_rag=True)
    4. История диалога
    """
    if not ai_client:
        return "⚠️ Ошибка: AI клиент не инициализирован."

    try:
        # ========== ШАГ 1: Сборка HUMANIZER_INSTRUCTIONS ==========
        humanizer = HUMANIZER_INSTRUCTIONS_TEMPLATE.format(
            bot_name=bot_record.name,
            company_name=bot_record.company_name or "TheCloser"
        )
        
        # ========== ШАГ 2: Получаем USER_PROMPT ==========
        user_prompt = bot_record.system_prompt or ""
        
        # ========== ШАГ 3: RAG CONTEXT (если включен) ==========
        rag_context = ""
        
        if bot_record.use_rag:
            logger.info(f"🔍 [Bot {bot_record.id}] Searching knowledge base...")
            rag_result = await get_rag_response(bot_record.id, message_text)
            
            if rag_result and rag_result.get('answer'):
                rag_context = f"\n\n📚 ИНФОРМАЦИЯ ИЗ БАЗЫ ЗНАНИЙ:\n{rag_result['answer']}\n"
                logger.info(f"✅ [Bot {bot_record.id}] RAG found info")
        
        # ========== ШАГ 4: Собираем FINAL_SYSTEM_PROMPT ==========
        final_system_prompt = humanizer + "\n\n" + user_prompt
        
        if rag_context:
            final_system_prompt += """

ВАЖНО: Используй информацию из базы знаний для ответа.
"""
            final_system_prompt += rag_context
        
        # ========== ШАГ 5: Формируем сообщения для OpenAI ==========
        messages_payload = [{"role": "system", "content": final_system_prompt}]
        
        # Добавляем историю
        if history:
            msgs_to_add = history
            if history and history[-1]['role'] == 'user' and history[-1]['content'] == message_text:
                msgs_to_add = history[:-1]
                
            messages_payload.extend(msgs_to_add)
            
        # Добавляем текущее сообщение
        messages_payload.append({"role": "user", "content": message_text})
        
        # ========== ШАГ 6: Запрос к OpenAI с ДИНАМИЧЕСКОЙ МОДЕЛЬЮ ==========
        loop = asyncio.get_event_loop()
        
        response = await loop.run_in_executor(
            None,
            lambda: ai_client.chat.completions.create(
                model=bot_record.openai_model,  # ← ДИНАМИЧЕСКАЯ МОДЕЛЬ
                messages=messages_payload,
                temperature=bot_record.temperature,
                max_tokens=bot_record.max_tokens
            )
        )
        
        answer = response.choices[0].message.content.strip()
        logger.info(f"🤖 [Bot {bot_record.name}] Model: {bot_record.openai_model}, Temp: {bot_record.temperature}")
        
        return answer
        
    except Exception as e:
        logger.error(f"OpenAI Error: {e}")
        return "Извините, я сейчас не могу ответить. Попробуйте позже."


# ==========================================
# Bot Behavior
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
    """Обработчик сообщений с HUMANIZER + RAG"""
    
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
    
    history = await get_conversation_history(conversation.id, limit=11)

    # --- ЭМУЛЯЦИЯ ЧЕЛОВЕКА ---
    
    # 1. Задержка чтения
    read_delay = 5 + random.randint(0, 5)
    await asyncio.sleep(read_delay)

    # 2. Прочитано
    try:
        await event.message.mark_read()
    except:
        pass
    
    # 3. Генерация ответа с HUMANIZER + RAG
    response_text = await get_chatgpt_response(
        text, 
        bot_record,
        history=history
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
    
    logger.info(f"✅ [{bot_record.name}] Replied to {user_name} (RAG: {bot_record.use_rag})")


# ==========================================
# Process Management
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
        logger.info(f"🚀 Bot started: {bot_record.name} (@{me.username}) | Model: {bot_record.openai_model} | {rag_status}")

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
    logger.info(f"🤖 HUMANIZER Instructions: ENABLED")
    
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