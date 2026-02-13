# services/functions_service.py
"""
Сервис для исполнения Function Calling.
ИСПРАВЛЕНО: Разделение Sync (БД) и Async (Telegram) для предотвращения ошибок Event Loop.
"""

import logging
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)

class FunctionsService:
    
    async def execute_function(self, bot_id: int, conversation_id: int, function_name: str, arguments: dict, client=None):
        """
        Точка входа. Асинхронная, работает в основном цикле событий.
        """
        try:
            # 1. Получаем информацию о функции из БД (в отдельном потоке)
            func_data = await self._db_get_function(bot_id, function_name)
            
            if not func_data:
                return {'success': False, 'error': f'Function {function_name} not found'}
            
            logger.info(f"🔧 [Bot {bot_id}] Executing: {function_name} ({func_data['type']})")
            
            # 2. Вызываем нужный обработчик (они тоже асинхронные)
            if func_data['type'] == 'save_lead':
                return await self._process_save_lead(bot_id, conversation_id, arguments, client)
            
            elif func_data['type'] == 'call_manager':
                return await self._process_call_manager(bot_id, conversation_id, arguments, client)
            
            else:
                return {'success': False, 'error': f"Unknown type: {func_data['type']}"}

        except Exception as e:
            logger.error(f"❌ Critical Function Error: {e}")
            return {'success': False, 'error': str(e)}

    # ==========================================
    # ЛОГИЧЕСКИЕ ОБРАБОТЧИКИ (ASYNC)
    # ==========================================
    
    async def _process_save_lead(self, bot_id, conversation_id, arguments, client):
        """Обработка сохранения лида"""
        # Сначала сохраняем в БД (синхронная часть)
        result = await self._db_save_lead(bot_id, conversation_id, arguments)
        
        if not result['success']:
            return result

        # Формируем текст
        text = f"🔔 **НОВЫЙ ЛИД!**\n\n"
        text += f"👤 **Клиент:** {result['user_name'] or 'Без имени'}\n"
        text += f"🆔 **ID:** `{result['user_id']}`\n"
        for k, v in arguments.items():
            text += f"🔹 {k}: {v}\n"
        text += f"\n🔗 https://thecloser.uz/dashboard/conversations/{result['conv_id']}"

        # Отправляем уведомление (асинхронная часть в основном цикле)
        await self._send_notification(client, result['recipient'], text)
        
        return {'success': True, 'message': 'Лид сохранен.'}

    async def _process_call_manager(self, bot_id, conversation_id, arguments, client):
        """Обработка вызова менеджера"""
        # Получаем данные диалога из БД
        data = await self._db_get_bot_context(bot_id, conversation_id)
        
        if not data:
            return {'success': False, 'error': 'Context not found'}

        reason = arguments.get('reason', 'Не указана')
        
        text = f"🆘 **ВЫЗОВ МЕНЕДЖЕРА**\n\n"
        text += f"👤 **Клиент:** {data['user_name']} (@{data['user_id']})\n"
        text += f"❓ **Причина:** {reason}\n"
        text += f"\n🔗 https://thecloser.uz/dashboard/conversations/{data['conv_id']}"
        
        await self._send_notification(client, data['recipient'], text)
        
        return {'success': True, 'message': 'Менеджер уведомлен.'}

    async def _send_notification(self, client, recipient, text):
        """
        Отправка сообщения через Telethon.
        Выполняется в том же Event Loop, что и run_bots.py -> НИКАКИХ ОШИБОК!
        """
        target = recipient if recipient else 'me'
        if target != 'me' and target.startswith('@'): 
            target = target.strip() # Telethon понимает и с @ и без

        if client and client.is_connected():
            try:
                await client.send_message(target, text)
                logger.info(f"✅ Notification sent to {target}")
            except Exception as e:
                logger.error(f"❌ Failed to send notification to {target}: {e}")
        else:
            logger.warning("⚠️ No active client to send notification")

    # ==========================================
    # DATABASE HELPERS (SYNC TO ASYNC)
    # ==========================================
    
    @sync_to_async
    def _db_get_function(self, bot_id, name):
        from core.models import BotFunction
        try:
            func = BotFunction.objects.get(bot_id=bot_id, name=name, is_active=True)
            return {'type': func.function_type}
        except BotFunction.DoesNotExist:
            return None

    @sync_to_async
    def _db_save_lead(self, bot_id, conversation_id, arguments):
        from core.models import BotAgent, Conversation
        try:
            bot = BotAgent.objects.get(id=bot_id)
            conv = Conversation.objects.get(id=conversation_id)
            
            conv.is_lead = True
            conv.lead_phone = arguments.get('phone', arguments.get('телефон', ''))
            conv.lead_data = arguments
            conv.save()
            
            return {
                'success': True,
                'recipient': bot.notification_recipient,
                'user_name': conv.user_name,
                'user_id': conv.user_id,
                'conv_id': conv.id
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @sync_to_async
    def _db_get_bot_context(self, bot_id, conversation_id):
        from core.models import BotAgent, Conversation
        try:
            bot = BotAgent.objects.get(id=bot_id)
            conv = Conversation.objects.get(id=conversation_id)
            return {
                'recipient': bot.notification_recipient,
                'user_name': conv.user_name,
                'user_id': conv.user_id,
                'conv_id': conv.id
            }
        except Exception as e:
            logger.error(f"DB Context Error: {e}")
            return None

functions_service = FunctionsService()