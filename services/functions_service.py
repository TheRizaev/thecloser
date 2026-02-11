# services/functions_service.py
"""
Сервис для исполнения Function Calling с защитой от гонки диалогов
"""

import logging
import json
import asyncio
from typing import Dict, Any
from django.utils import timezone
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)


class FunctionsService:
    """
    Исполнение функций, вызванных AI
    """
    
    @sync_to_async
    def execute_function(self, bot_id: int, conversation_id: int, function_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Главный диспетчер функций.
        Теперь принимает conversation_id для точной идентификации диалога.
        """
        try:
            from core.models import BotFunction
            
            # Находим функцию
            func = BotFunction.objects.get(
                bot_id=bot_id,
                name=function_name,
                is_active=True
            )
            
            logger.info(f"🔧 [Bot {bot_id}] Executing function: {function_name} for Conversation {conversation_id}")
            logger.info(f"📦 Arguments: {arguments}")
            
            # Маршрутизация по типу
            if func.function_type == 'save_lead':
                return self._save_lead(bot_id, conversation_id, arguments)
            
            elif func.function_type == 'call_manager':
                return self._call_manager(bot_id, conversation_id, arguments)
            
            else:
                return {
                    'success': False,
                    'error': f'Unknown function type: {func.function_type}'
                }
                
        except BotFunction.DoesNotExist:
            logger.error(f"❌ Function '{function_name}' not found for bot {bot_id}")
            return {
                'success': False,
                'error': f'Function {function_name} not found'
            }
        except Exception as e:
            logger.error(f"❌ Error executing {function_name}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _save_lead(self, bot_id: int, conversation_id: int, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Сохранение лида в конкретный диалог (по ID)
        """
        from core.models import BotAgent, Conversation
        
        try:
            bot = BotAgent.objects.get(id=bot_id)
            
            # 1. ПОЛУЧАЕМ КОНКРЕТНЫЙ ДИАЛОГ ПО ID (ЗАЩИТА ОТ ОШИБОК)
            try:
                conv = Conversation.objects.get(id=conversation_id)
            except Conversation.DoesNotExist:
                logger.error(f"❌ Conversation {conversation_id} not found for save_lead")
                return {'success': False, 'error': 'Conversation not found'}
            
            # 2. ДИНАМИЧЕСКОЕ ИЗВЛЕЧЕНИЕ ПОЛЕЙ
            lead_data = {}
            for key, value in arguments.items():
                lead_data[key] = value
            
            logger.info(f"📦 Collected lead data: {lead_data}")
            
            # 3. ОБНОВЛЯЕМ ДАННЫЕ В БД
            conv.is_lead = True
            # Пытаемся найти телефон и email в любых полях
            conv.lead_phone = lead_data.get('phone', lead_data.get('телефон', lead_data.get('номер', '')))
            conv.lead_email = lead_data.get('email', lead_data.get('почта', lead_data.get('email', '')))
            
            # Сохраняем полный JSON
            conv.lead_data = lead_data
            conv.save()
            
            logger.info(f"✅ Lead saved for Conversation {conversation_id}")
            
            # 4. ФОРМИРУЕМ УВЕДОМЛЕНИЕ
            notification_lines = ["🔔 **НОВЫЙ ЛИД!**\n"]
            
            # Маппинг emoji
            emoji_map = {
                'name': '👤', 'имя': '👤', 'фио': '👤',
                'phone': '📞', 'телефон': '📞', 'номер': '📞',
                'email': '📧', 'почта': '📧',
                'comment': '💬', 'комментарий': '💬',
                'date': '📅', 'дата': '📅',
                'time': '🕐', 'время': '🕐',
                'budget': '💰', 'бюджет': '💰',
            }
            
            for field_name, field_value in lead_data.items():
                emoji = emoji_map.get(field_name.lower(), '📌')
                field_label = field_name.replace('_', ' ').capitalize()
                notification_lines.append(f"{emoji} **{field_label}:** {field_value}")
            
            notification_lines.append(f"\n🤖 **Бот:** {bot.name}")
            notification_lines.append(f"🔗 **Диалог:** https://yoursite.com/dashboard/conversations/{conv.id}")
            
            notification_text = "\n".join(notification_lines)
            
            # Отправляем уведомление владельцу
            self._send_telegram_notification(bot, notification_text)
            
            return {
                'success': True,
                'message': 'Данные успешно сохранены.',
                'lead_data': lead_data
            }
            
        except Exception as e:
            logger.error(f"❌ Error saving lead: {e}")
            return {
                'success': False,
                'error': 'Не удалось сохранить данные'
            }
    
    def _call_manager(self, bot_id: int, conversation_id: int, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Вызов менеджера для конкретного диалога
        """
        from core.models import BotAgent, Conversation
        
        try:
            bot = BotAgent.objects.get(id=bot_id)
            
            # Получаем диалог
            try:
                conv = Conversation.objects.get(id=conversation_id)
            except Conversation.DoesNotExist:
                return {'success': False, 'error': 'Conversation not found'}
            
            reason = arguments.get('reason', 'Клиент требует человека')
            
            # 🆘 ФОРМИРУЕМ УВЕДОМЛЕНИЕ
            notification_text = f"""
🆘 **ТРЕБУЕТСЯ ЧЕЛОВЕК!**

👤 **Юзер:** @{conv.user_id} ({conv.user_name})

📋 **Ситуация:**
{reason}

🤖 **Бот:** {bot.name}
🔗 **Диалог:** https://yoursite.com/dashboard/conversations/{conv.id}

⏰ {timezone.now().strftime('%d.%m.%Y %H:%M')}
            """.strip()
            
            self._send_telegram_notification(bot, notification_text)
            
            logger.info(f"🆘 Manager called for Conversation {conversation_id}")
            
            return {
                'success': True,
                'message': 'Менеджер уведомлен.'
            }
            
        except Exception as e:
            logger.error(f"❌ Error calling manager: {e}")
            return {'success': False, 'error': 'Ошибка вызова менеджера'}
    
    def _send_telegram_notification(self, bot, text: str):
        """
        Отправка уведомления владельцу через Telegram (в Saved Messages)
        """
        from telethon import TelegramClient
        from telethon.sessions import StringSession
        
        try:
            if not bot.session_string:
                return
            
            async def send_to_saved():
                try:
                    client = TelegramClient(
                        StringSession(bot.session_string),
                        int(bot.api_id),
                        bot.api_hash
                    )
                    await client.connect()
                    await client.send_message('me', text)
                    await client.disconnect()
                except Exception as inner_e:
                    logger.error(f"Send error: {inner_e}")
            
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            loop.create_task(send_to_saved())
            
        except Exception as e:
            logger.error(f"❌ Failed to send Telegram notification: {e}")


# Глобальный экземпляр
functions_service = FunctionsService()