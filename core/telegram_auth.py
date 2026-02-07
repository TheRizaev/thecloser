# core/telegram_auth.py
from telethon import TelegramClient
from telethon.errors import (
    SessionPasswordNeededError, 
    PhoneCodeInvalidError, 
    PhoneCodeExpiredError,
    FloodWaitError
)
from telethon.sessions import StringSession
import logging
import os
import tempfile

logger = logging.getLogger(__name__)


async def send_code_request(phone_number, api_id, api_hash):
    """Отправка кода через Telethon"""
    
    # Гарантируем int
    try:
        api_id_int = int(api_id) if not isinstance(api_id, int) else api_id
    except (ValueError, TypeError) as e:
        return {'success': False, 'error': f'API ID должен быть числом: {e}'}
    
    # Временная директория для сессии
    temp_dir = tempfile.gettempdir()
    session_file = os.path.join(temp_dir, f"thecloser_session_{api_id_int}_{hash(phone_number) & 0xFFFFFFFF}")
    
    # Удаляем старую сессию если есть
    for ext in ['', '.session', '.session-journal']:
        try:
            if os.path.exists(session_file + ext):
                os.remove(session_file + ext)
        except:
            pass
    
    client = TelegramClient(session_file, api_id_int, str(api_hash).strip())
    
    try:
        await client.connect()
        
        # Отправляем код
        result = await client.send_code_request(str(phone_number).strip())
        
        # ВАЖНО: Получаем строку сессии ПОСЛЕ отправки кода
        # В Telethon с SQLiteSession это путь к файлу
        session_string = session_file  # Сохраняем путь к файлу для следующего шага
        
        await client.disconnect()
        
        logger.info(f"Code sent, session file: {session_file}")
        
        return {
            'success': True,
            'phone_code_hash': result.phone_code_hash,
            'temp_session_string': session_string  # Путь к файлу сессии
        }
        
    except FloodWaitError as e:
        minutes = e.seconds // 60
        return {
            'success': False,
            'error': f'⏳ Подождите {minutes} мин. перед повторной попыткой'
        }
    except Exception as e:
        logger.error(f"Error in send_code_request: {e}")
        try:
            await client.disconnect()
        except:
            pass
        return {'success': False, 'error': str(e)}


async def verify_code(phone_number, phone_code_hash, code, api_id, api_hash, temp_session_string, password=None):
    """Проверка кода через Telethon"""
    
    logger.info(f"DEBUG verify_code: session_file={temp_session_string}")
    
    # Проверяем существование файла сессии
    if not temp_session_string or not os.path.exists(temp_session_string):
        # Попробуем найти с расширением .session
        session_with_ext = temp_session_string + '.session' if temp_session_string else None
        if session_with_ext and os.path.exists(session_with_ext):
            temp_session_string = session_with_ext.replace('.session', '')
        else:
            return {'success': False, 'error': 'Файл сессии не найден. Начните сначала.'}
    
    try:
        api_id_int = int(api_id) if not isinstance(api_id, int) else api_id
    except (ValueError, TypeError) as e:
        return {'success': False, 'error': f'API ID должен быть числом: {e}'}
    
    session_file = temp_session_string  # Это путь к файлу БЕЗ расширения
    
    client = TelegramClient(session_file, api_id_int, str(api_hash).strip())
    
    try:
        await client.connect()
        
        # Проверяем, не авторизованы ли уже
        if await client.is_user_authorized():
            logger.info("Already authorized, exporting session...")
            # Уже авторизованы - экспортируем строку
            session_string = StringSession.save(client.session)
            await client.disconnect()
            return {'success': True, 'session_string': session_string}
        
        # Входим с кодом
        logger.info(f"Signing in with code: {code}")
        await client.sign_in(
            phone=str(phone_number).strip(),
            code=code,
            phone_code_hash=phone_code_hash
        )
        
        # Проверяем авторизацию ПОСЛЕ входа
        if not await client.is_user_authorized():
            await client.disconnect()
            return {'success': False, 'error': 'Не удалось авторизоваться'}
        
        # Экспортируем session string для хранения в БД
        # Используем StringSession для создания переносимой строки
        session_string = StringSession.save(client.session)
        
        logger.info(f"Session string exported, length: {len(session_string) if session_string else 0}")
        
        await client.disconnect()
        
        # Очищаем временные файлы
        for ext in ['', '.session', '.session-journal']:
            try:
                if os.path.exists(session_file + ext):
                    os.remove(session_file + ext)
            except:
                pass
        
        if not session_string:
            return {'success': False, 'error': 'Не удалось получить session string'}
        
        return {
            'success': True,
            'session_string': session_string  # Это строка для хранения в БД
        }
        
    except SessionPasswordNeededError:
        if password:
            try:
                await client.sign_in(password=password)
                
                # Проверяем авторизацию
                if not await client.is_user_authorized():
                    await client.disconnect()
                    return {'success': False, 'error': 'Не удалось авторизоваться с 2FA'}
                
                session_string = StringSession.save(client.session)
                await client.disconnect()
                
                # Очистка
                for ext in ['', '.session', '.session-journal']:
                    try:
                        if os.path.exists(session_file + ext):
                            os.remove(session_file + ext)
                    except:
                        pass
                
                if not session_string:
                    return {'success': False, 'error': 'Не удалось получить session string'}
                
                return {'success': True, 'session_string': session_string}
                
            except Exception as e:
                await client.disconnect()
                return {'success': False, 'error': f'Ошибка 2FA: {str(e)}'}
        else:
            await client.disconnect()
            return {'success': False, 'error': '🔐 Нужен 2FA пароль', 'requires_2fa': True}
            
    except PhoneCodeInvalidError:
        await client.disconnect()
        return {'success': False, 'error': '❌ Неверный код'}
        
    except PhoneCodeExpiredError:
        await client.disconnect()
        return {'success': False, 'error': '⏰ Код истёк'}
        
    except Exception as e:
        logger.error(f"Error in verify_code: {e}")
        try:
            await client.disconnect()
        except:
            pass
        return {'success': False, 'error': str(e)}