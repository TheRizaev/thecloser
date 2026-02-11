# services/functions_service.py
import logging
import asyncio
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)

class FunctionsService:
    """
    Сервис для выполнения функций.
    Умеет использовать активный Telethon Client для отправки уведомлений.
    """
    
    @sync_to_async
    def execute_function(self, bot_id: int, conversation_id: int, function_name: str, arguments: dict, client=None):
        try:
            from core.models import BotFunction
            
            # Получаем функцию из БД
            try:
                func = BotFunction.objects.get(bot_id=bot_id, name=function_name, is_active=True)
            except BotFunction.DoesNotExist:
                return {'success': False, 'error': f'Function {function_name} not found'}
            
            logger.info(f"🔧 [Bot {bot_id}] Executing: {function_name} | Args: {arguments}")
            
            if func.function_type == 'save_lead':
                return self._save_lead(bot_id, conversation_id, arguments, client)
            
            elif func.function_type == 'call_manager':
                return self._call_manager(bot_id, conversation_id, arguments, client)
            
            return {'success': False, 'error': f'Unknown function type: {func.function_type}'}
                
        except Exception as e:
            logger.error(f"❌ Function Execution Error: {e}")
            return {'success': False, 'error': str(e)}

    def _save_lead(self, bot_id, conversation_id, arguments, client):
        from core.models import BotAgent, Conversation
        try:
            bot = BotAgent.objects.get(id=bot_id)
            conv = Conversation.objects.get(id=conversation_id)
            
            # Сохранение данных лида
            conv.is_lead = True
            conv.lead_phone = arguments.get('phone', arguments.get('телефон', ''))
            conv.lead_data = arguments
            conv.save()
            
            # Текст уведомления
            text = f"🔔 **НОВЫЙ ЛИД!**\n\n"
            text += f"👤 **Клиент:** {conv.user_name or 'Без имени'}\n"
            text += f"🆔 **ID:** `{conv.user_id}`\n"
            for k, v in arguments.items():
                text += f"🔹 {k}: {v}\n"
            text += f"\n🔗 https://thecloser.uz/dashboard/conversations/{conv.id}"
            
            # Отправка
            self._send_notification(bot, text, client)
            
            return {'success': True, 'message': 'Лид успешно сохранен.'}
        except Exception as e:
            logger.error(f"Save Lead Error: {e}")
            return {'success': False, 'error': 'Ошибка сохранения данных'}

    def _call_manager(self, bot_id, conversation_id, arguments, client):
        from core.models import BotAgent, Conversation
        try:
            bot = BotAgent.objects.get(id=bot_id)
            conv = Conversation.objects.get(id=conversation_id)
            
            reason = arguments.get('reason', 'Клиент запросил человека')
            
            text = f"🆘 **ТРЕБУЕТСЯ МЕНЕДЖЕР**\n\n"
            text += f"👤 **Клиент:** {conv.user_name} (@{conv.user_id})\n"
            text += f"❓ **Причина:** {reason}\n"
            text += f"\n🔗 https://thecloser.uz/dashboard/conversations/{conv.id}"
            
            self._send_notification(bot, text, client)
            
            return {'success': True, 'message': 'Менеджер уведомлен.'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _send_notification(self, bot, text, client):
        """
        Отправляет уведомление.
        1. Если задан notification_recipient -> шлет туда.
        2. Если нет -> шлет в 'me' (Избранное).
        3. Использует client из run_bots.py, чтобы не было конфликта сессий.
        """
        target = 'me'
        if bot.notification_recipient:
            target = bot.notification_recipient.strip()
            # Telethon нормально ест юзернеймы и с @ и без, но можно почистить
            if target.startswith('@'): target = target
        
        logger.info(f"📨 Отправка уведомления получателю: {target}")

        # Сценарий 1: У нас есть активный клиент (от бота)
        if client and client.is_connected():
            async def send_now():
                try:
                    await client.send_message(target, text)
                    logger.info(f"✅ Уведомление отправлено ({target}) через активную сессию")
                except Exception as e:
                    logger.error(f"❌ Ошибка отправки (активная сессия): {e}")
            
            # Добавляем задачу в текущий цикл событий
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(send_now())
            except RuntimeError:
                # Если цикла нет (странно, но бывает), запускаем
                asyncio.run(send_now())
            return

        # Сценарий 2: Клиента нет (fallback, опасно, может конфликтовать)
        if bot.session_string:
            from telethon import TelegramClient
            from telethon.sessions import StringSession
            
            async def send_new():
                try:
                    c = TelegramClient(StringSession(bot.session_string), int(bot.api_id), bot.api_hash)
                    await c.connect()
                    await c.send_message(target, text)
                    await c.disconnect()
                    logger.info(f"✅ Уведомление отправлено ({target}) через новую сессию")
                except Exception as e:
                    logger.error(f"❌ Ошибка отправки (новая сессия): {e}")
            
            try:
                loop = asyncio.get_event_loop()
                loop.create_task(send_new())
            except:
                pass

functions_service = FunctionsService()