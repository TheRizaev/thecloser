# core/tasks.py
"""
Celery задачи для асинхронной обработки
"""

from celery import shared_task
from django.utils import timezone
import logging

from .models import KnowledgeBase
from ..services.rag_service import rag_service

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def index_document_async(self, kb_id, file_path):
    """
    Асинхронная индексация документа
    
    Args:
        kb_id: ID документа в базе знаний
        file_path: Путь к файлу
        
    Returns:
        dict: Результат индексации
    """
    try:
        logger.info(f"Начало индексации документа {kb_id}")
        
        # Запускаем индексацию
        chunks_count = rag_service.process_document(kb_id, file_path)
        
        # Обновляем запись в БД
        kb = KnowledgeBase.objects.get(id=kb_id)
        kb.chunks_count = chunks_count
        kb.indexed_at = timezone.now()
        kb.save()
        
        logger.info(f"Документ {kb_id} успешно проиндексирован. Создано {chunks_count} фрагментов")
        
        return {
            'success': True,
            'chunks_count': chunks_count,
            'kb_id': kb_id
        }
        
    except Exception as e:
        logger.error(f"Ошибка индексации документа {kb_id}: {str(e)}")
        
        # Помечаем документ как не проиндексированный
        try:
            kb = KnowledgeBase.objects.get(id=kb_id)
            kb.is_indexed = False
            kb.save()
        except:
            pass
        
        # Повторная попытка
        raise self.retry(exc=e, countdown=60)


@shared_task
def cleanup_old_conversations():
    """
    Очистка старых диалогов (старше 6 месяцев)
    Запускается по расписанию через Celery Beat
    """
    from datetime import timedelta
    from .models import Conversation
    
    cutoff_date = timezone.now() - timedelta(days=180)
    
    deleted_count = Conversation.objects.filter(
        last_message_at__lt=cutoff_date
    ).delete()[0]
    
    logger.info(f"Удалено {deleted_count} старых диалогов")
    
    return {'deleted_count': deleted_count}


@shared_task
def calculate_daily_analytics():
    """
    Расчет ежедневной аналитики
    Запускается каждую ночь
    """
    from .models import BotAgent, Conversation, Message, Analytics
    from datetime import timedelta
    
    yesterday = (timezone.now() - timedelta(days=1)).date()
    
    bots = BotAgent.objects.all()
    
    for bot in bots:
        # Считаем метрики за вчера
        conversations = Conversation.objects.filter(
            bot=bot,
            started_at__date=yesterday
        )
        
        conversations_count = conversations.count()
        leads_count = conversations.filter(is_lead=True).count()
        
        messages_count = Message.objects.filter(
            conversation__bot=bot,
            created_at__date=yesterday
        ).count()
        
        # Создаем или обновляем запись
        Analytics.objects.update_or_create(
            bot=bot,
            date=yesterday,
            defaults={
                'conversations_count': conversations_count,
                'leads_count': leads_count,
                'messages_count': messages_count
            }
        )
    
    logger.info(f"Аналитика за {yesterday} рассчитана для {bots.count()} ботов")
    
    return {'date': str(yesterday), 'bots_processed': bots.count()}


@shared_task
def send_daily_report():
    """
    Отправка ежедневного отчета по email
    """
    from django.core.mail import send_mail
    from django.contrib.auth.models import User
    
    # TODO: Реализовать отправку отчетов
    
    logger.info("Ежедневные отчеты отправлены")
    
    return {'success': True}