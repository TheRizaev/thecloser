# core/telegram_session.py
from telethon import TelegramClient
from telethon.sessions import StringSession
import logging

logger = logging.getLogger(__name__)


class TelegramSessionManager:
    """Менеджер для Telethon сессий"""
    
    @staticmethod
    async def validate_session_string(session_string: str, api_id, api_hash) -> bool:
        """Проверка валидности session string"""
        try:
            api_id_int = int(api_id) if not isinstance(api_id, int) else api_id
            
            # StringSession для строки, не файла
            session = StringSession(session_string)
            client = TelegramClient(session, api_id_int, str(api_hash))
            
            await client.connect()
            me = await client.get_me()
            logger.info(f"Valid session for: {me.first_name}")
            await client.disconnect()
            return True
            
        except Exception as e:
            logger.error(f"Invalid session: {e}")
            return False
    
    @staticmethod
    async def get_account_info(session_string: str, api_id, api_hash) -> dict:
        """Получение информации об аккаунте"""
        try:
            api_id_int = int(api_id) if not isinstance(api_id, int) else api_id
            
            session = StringSession(session_string)
            client = TelegramClient(session, api_id_int, str(api_hash))
            
            await client.connect()
            me = await client.get_me()
            
            await client.disconnect()
            
            return {
                'success': True,
                'user': {
                    'id': me.id,
                    'first_name': me.first_name,
                    'last_name': me.last_name,
                    'username': me.username,
                    'phone': me.phone
                }
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}