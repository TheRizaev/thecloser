# run_bots.py
#!/usr/bin/env python
"""
The Closer Worker - С ПОДДЕРЖКОЙ НОВОГО API и передачей активного клиента
+ ФУНКЦИЯ ПОСЛЕДНЕГО СООБЩЕНИЯ (Debounce)
"""
import asyncio
import os
import sys
import django
import logging
import random
from asgiref.sync import sync_to_async
import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- DUMMY SERVER для Health Checks (Render/Railway) ---
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

# --- DJANGO SETUP ---
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

# --- LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("BotWorker")

# --- OPENAI SETUP ---
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

# Глобальный словарь для накопления сообщений: {(bot_id, user_id): {'messages': [], 'task': Task}}
accumulators = {}
# Время ожидания следующего сообщения (в секундах)
MESSAGE_DEBOUNCE_DELAY = 15 

# --- PROMPT TEMPLATES ---
HUMANIZER_INSTRUCTIONS_TEMPLATE = """
Роль: Ты — {bot_name}, сотрудник {company_name}. Пишешь с телефона в Telegram.
Задача: Решить вопрос или продать.

СТИЛЬ (СТРОГО):
1. **Формат:** Пиши предельно кратко. Избегай списков. Короткие фразы — без точки в конце, можно с маленькой буквы.
2. **Табу:** ЗАПРЕЩЕНО писать "Я ИИ", "Языковая модель", "Чем могу помочь?".
3. **Реакция:** На "Привет" отвечай "Привет" или "На связи". Не задавай вопросов, пока не поймешь суть.
4. **Конкретика:** Не зеркаль вопрос (User: "Цена?" -> Bot: "5000", а не "Цена составляет...").
5. **Мульти-вопросы:** Если пользователь задал несколько вопросов подряд, отвечай на них по порядку, разделяя ответы пустой строкой (абзацами). Если это одна мысль — отвечай одним блоком.

Веди себя как занятой человек, а не как услужливый робот.
"""

# --- DATABASE HELPERS ---

@sync_to_async
def get_active_bots_from_db():
    return list(BotAgent.objects.filter(
        platform='telegram',
        status='active'
    ).exclude(session_string='').exclude(session_string__isnull=True))

@sync_to_async
def get_bot_by_id(bot_id):
    try:
        return BotAgent.objects.get(id=bot_id)
    except BotAgent.DoesNotExist:
        return None

@sync_to_async
def get_or_create_conversation(bot_instance, user_id, user_name):
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
    return MessageModel.objects.create(
        conversation=conversation,
        role=role,
        content=content
    )

@sync_to_async
def mark_bot_invalid(bot_id):
    BotAgent.objects.filter(id=bot_id).update(status='error')

@sync_to_async
def get_conversation_history(conversation_id, limit=10):
    messages = MessageModel.objects.filter(conversation_id=conversation_id).order_by('-created_at')[:limit]
    history_objs = list(reversed(messages))
    
    formatted_history = []
    for msg in history_objs:
        role = 'assistant' if msg.role == 'bot' else 'user'
        formatted_history.append({'role': role, 'content': msg.content})
        
    return formatted_history

@sync_to_async
def get_rag_response(bot_id, query):
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

# --- AI CORE LOGIC ---

async def get_chatgpt_response(message_text, bot_record, history=None, conversation_id=None, telegram_client=None):
    """
    Генерация ответа с поддержкой Function Calling и Humanizer.
    telegram_client: Активное соединение для отправки уведомлений без конфликтов.
    """
    if not ai_client:
        return "⚠️ Ошибка: AI клиент не инициализирован."

    try:
        from core.models import BotFunction
        from services.functions_service import functions_service
        
        # 1. Humanizer (Личность бота)
        humanizer = HUMANIZER_INSTRUCTIONS_TEMPLATE.format(
            bot_name=bot_record.name,
            company_name=bot_record.company_name or "TheCloser"
        )
        
        user_prompt = bot_record.system_prompt or ""
        
        # 2. RAG (База знаний)
        rag_context = ""
        if bot_record.use_rag:
            logger.info(f"🔍 [Bot {bot_record.id}] Searching knowledge base...")
            rag_result = await get_rag_response(bot_record.id, message_text)
            
            if rag_result and rag_result.get('answer'):
                rag_context = f"\n\n📚 ИНФОРМАЦИЯ ИЗ БАЗЫ ЗНАНИЙ:\n{rag_result['answer']}\n"
                logger.info(f"✅ [Bot {bot_record.id}] RAG found info")
        
        # 3. Сборка финального промпта
        final_system_prompt = humanizer + "\n\n" + user_prompt
        if rag_context:
            final_system_prompt += "\n\nВАЖНО: Используй информацию из базы знаний для ответа."
            final_system_prompt += rag_context
        
        # Формируем историю сообщений
        messages_payload = [{"role": "system", "content": final_system_prompt}]
        
        if history:
            msgs_to_add = history
            # Исключаем дублирование последнего сообщения, если оно уже там
            if history and history[-1]['role'] == 'user' and history[-1]['content'] == message_text:
                msgs_to_add = history[:-1]
            messages_payload.extend(msgs_to_add)
        
        messages_payload.append({"role": "user", "content": message_text})
        
        # 4. Загрузка инструментов (Functions)
        bot_functions = await sync_to_async(list)(
            BotFunction.objects.filter(bot=bot_record, is_active=True)
        )
        tools = [func.to_openai_tool() for func in bot_functions]
        
        logger.info(f"[Bot {bot_record.name}] Model: {bot_record.openai_model} | Tools: {len(tools)}")
        
        loop = asyncio.get_event_loop()
        uses_new_api = bot_record.uses_new_api()
        
        # Параметры API запроса
        api_params = {
            "model": bot_record.openai_model,
            "messages": messages_payload,
        }
        if tools:
            api_params["tools"] = tools
            api_params["tool_choice"] = "auto"
            
        if not uses_new_api:
             api_params["temperature"] = bot_record.temperature
             api_params["max_tokens"] = bot_record.max_tokens

        # 5. ПЕРВЫЙ ЗАПРОС К OPENAI
        response = await loop.run_in_executor(
            None,
            lambda: ai_client.chat.completions.create(**api_params)
        )
        
        message = response.choices[0].message
        
        # 6. ОБРАБОТКА FUNCTION CALLING
        if message.tool_calls:
            logger.info(f"🔧 [Bot {bot_record.id}] AI wants to call {len(message.tool_calls)} function(s)")
            
            messages_payload.append(message)
            
            for tool_call in message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                logger.info(f"⚙️ Calling: {function_name} with {function_args}")
                
                result = await functions_service.execute_function(
                    bot_record.id,
                    conversation_id,
                    function_name,
                    function_args,
                    client=telegram_client  # <--- ПЕРЕДАЕМ ТРУБКУ
                )
                
                messages_payload.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": function_name,
                    "content": json.dumps(result, ensure_ascii=False)
                })
            
            # 7. ВТОРОЙ ЗАПРОС К OPENAI (Финальный ответ)
            final_api_params = {
                "model": bot_record.openai_model,
                "messages": messages_payload
            }
            if not uses_new_api:
                final_api_params["temperature"] = bot_record.temperature
                final_api_params["max_tokens"] = bot_record.max_tokens
                
            final_response = await loop.run_in_executor(
                None,
                lambda: ai_client.chat.completions.create(**final_api_params)
            )
            
            return final_response.choices[0].message.content.strip()
        
        return message.content.strip()
        
    except Exception as e:
        logger.error(f"OpenAI Error: {e}")
        return "Извините, я сейчас не могу ответить. Попробуйте позже."


# --- TELETHON HANDLERS ---

async def keep_online_loop(client, bot_name):
    while True:
        try:
            await client(functions.account.UpdateStatusRequest(offline=False))
        except Exception as e:
            logger.error(f"[{bot_name}] Failed to update status: {e}")
        
        await asyncio.sleep(300 + random.randint(0, 10))


async def process_accumulated_messages(bot_record, user_id, conversation, client, chat_id):
    """
    Асинхронная задача для обработки накопленных сообщений.
    Ждет DEBOUNCE время, затем отвечает на все сразу.
    """
    key = (bot_record.id, user_id)
    
    try:
        await asyncio.sleep(MESSAGE_DEBOUNCE_DELAY)
    except asyncio.CancelledError:
        return

    if key not in accumulators:
        return
        
    messages_to_process = accumulators[key]['messages']
    del accumulators[key]
    
    if not messages_to_process:
        return

    combined_text = "\n\n".join(messages_to_process)
    logger.info(f"🧩 [{bot_record.name}] Processing group of {len(messages_to_process)} messages. Total length: {len(combined_text)}")

    raw_history = await get_conversation_history(conversation.id, limit=20)
    
    history_for_ai = raw_history
    if len(raw_history) >= len(messages_to_process):
        match = True
        for i in range(1, len(messages_to_process) + 1):
            if raw_history[-i]['content'] != messages_to_process[-i]:
                match = False
                break
        
        if match:
            history_for_ai = raw_history[:-len(messages_to_process)]

    response_text = await get_chatgpt_response(
        combined_text, 
        bot_record,
        history=history_for_ai,
        conversation_id=conversation.id,
        telegram_client=client
    )

    # 5. Имитация печати и отправка
    typing_speed = random.randint(5, 8)
    typing_duration = len(response_text) / typing_speed
    typing_duration = max(2.0, min(15.0, typing_duration))

    try:
        async with client.action(chat_id, 'typing'):
            await asyncio.sleep(typing_duration)
    except:
        await asyncio.sleep(typing_duration)

    try:
        await client.send_message(chat_id, response_text)
        await save_message_to_db(conversation, 'bot', response_text)
        logger.info(f"✅ [{bot_record.name}] Replied to group messages")
    except Exception as e:
        logger.error(f"❌ Failed to send reply: {e}")


async def handle_message(event, bot_id):
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

    conversation = await get_or_create_conversation(bot_record, user_id, user_name)
    await save_message_to_db(conversation, 'user', text)    
    
    read_delay = 2 + random.randint(0, 3)
    asyncio.create_task(mark_read_delayed(event, read_delay))

    key = (bot_id, user_id)
    
    if key in accumulators:
        accumulators[key]['task'].cancel()
        accumulators[key]['messages'].append(text)
    else:
        accumulators[key] = {
            'messages': [text],
            'task': None
        }
    
    # Запускаем новый таймер
    task = asyncio.create_task(
        process_accumulated_messages(bot_record, user_id, conversation, event.client, event.chat_id)
    )
    accumulators[key]['task'] = task


async def mark_read_delayed(event, delay):
    """Отдельная задача для отметки прочтения"""
    await asyncio.sleep(delay)
    try:
        await event.message.mark_read()
    except:
        pass


async def start_single_bot(bot_record):
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
        api_type = "🧠 NEW API" if bot_record.uses_new_api() else "🔧 LEGACY API"
        logger.info(f"🚀 Bot started: {bot_record.name} (@{me.username}) | {bot_record.openai_model} | {api_type} | {rag_status}")

    except Exception as e:
        logger.error(f"❌ Error starting bot {bot_record.name}: {e}")


async def stop_single_bot(bot_id):
    if bot_id in active_clients:
        data = active_clients[bot_id]
        
        for task in data.get('tasks', []):
            task.cancel()
        
        client = data['client']
        await client.disconnect()
        
        del active_clients[bot_id]
        logger.info(f"🛑 Bot ID {bot_id} stopped")


async def monitor_manager():
    logger.info("👀 Monitor Manager started...")
    logger.info(f"📚 RAG Service: {'✅ Available' if rag_service else '❌ Not available'}")
    logger.info(f"🤖 HUMANIZER: ENABLED with Group Response")
    logger.info(f"⏱️ DEBOUNCE DELAY: {MESSAGE_DEBOUNCE_DELAY}s")
    
    while True:
        try:
            db_bots = await get_active_bots_from_db()
            db_bot_ids = set(b.id for b in db_bots)
            running_ids = set(active_clients.keys())

            for bot_id in (db_bot_ids - running_ids):
                bot_obj = next(b for b in db_bots if b.id == bot_id)
                asyncio.create_task(start_single_bot(bot_obj))

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