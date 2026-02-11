# core/models.py - ПОЛНАЯ ВЕРСИЯ СО ВСЕМИ МОДЕЛЯМИ
# ОБНОВЛЕНО: Возвращены o1, o3, GPT-5+ с маркерами для нового API

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from pgvector.django import VectorField
import re

# ============================================
# HELPER FUNCTIONS
# ============================================

def knowledge_base_upload_path(instance, filename):
    """Генерирует путь для загрузки: knowledge_base/user_email/filename"""
    user_email = instance.user.email.split('@')[0]
    clean_email = re.sub(r'[^\w\-.]', '_', user_email)
    clean_filename = re.sub(r'[^\w\-.]', '_', filename)
    return f'knowledge_base/{clean_email}/{clean_filename}'

# ============================================
# МОДЕЛЬ: БОТ-АССИСТЕНТ (ПОЛНАЯ ВЕРСИЯ)
# ============================================

class BotAgent(models.Model):
    """Модель бота-ассистента"""
    
    PLATFORM_CHOICES = [
        ('telegram', 'Telegram'),
        ('whatsapp', 'WhatsApp'),
        ('instagram', 'Instagram'),
        ('vk', 'VK'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Активен'),
        ('paused', 'На паузе'),
        ('inactive', 'Неактивен'),
        ('waiting_code', 'Ожидание кода'),
        ('error', 'Ошибка'),
    ]
    
    # ========== ПОЛНЫЙ СПИСОК МОДЕЛЕЙ (Legacy + Reasoning + Future) ==========
    MODEL_CHOICES = [
        # ===== GPT-3.5 (Legacy, Дешевые) =====
        ('gpt-3.5-turbo', 'GPT-3.5 Turbo (Cheap)'),
        ('gpt-3.5-turbo-0125', 'GPT-3.5 Turbo 0125 (Cheap)'),
        
        # ===== GPT-4 Turbo (Умеренные) =====
        ('gpt-4-turbo', 'GPT-4 Turbo (Moderate)'),
        ('gpt-4-turbo-2024-04-09', 'GPT-4 Turbo (Apr 2024) (Moderate)'),
        
        # ===== GPT-4o (Умеренные - Рекомендуем) =====
        ('gpt-4o', 'GPT-4o (Moderate) ⭐'),
        ('gpt-4o-2024-11-20', 'GPT-4o (Nov 2024) (Moderate)'),
        ('gpt-4o-2024-08-06', 'GPT-4o (Aug 2024) (Moderate)'),
        ('gpt-4o-2024-05-13', 'GPT-4o (May 2024) (Moderate)'),
        
        # ===== GPT-4o mini (Дешевые - Оптимальные) =====
        ('gpt-4o-mini', 'GPT-4o mini (Cheap) 🔥'),
        ('gpt-4o-mini-2024-07-18', 'GPT-4o mini (Jul 2024) (Cheap)'),
        
        # ===== GPT-4 (Дорогие - Legacy) =====
        ('gpt-4', 'GPT-4 (Expensive)'),
        ('gpt-4-0613', 'GPT-4 0613 (Expensive)'),
        
        # ===== o1 REASONING MODELS (Очень дорогие) =====
        ('o1-mini-2024-09-12', 'o1 mini (Moderate) 🧠'),
        ('o1-2024-12-17', 'o1 (Very Expensive) 🧠'),
        
        # ===== o3 REASONING MODELS (Очень дорогие) =====
        ('o3-mini-2025-01-31', 'o3 mini (Moderate) 🧠'),
        
        # ===== GPT-4.1 =====
        ('gpt-4.1-2025-04-14', 'GPT-4.1 (Moderate)'),
        
        # ===== GPT-5 SERIES (Будущие модели) =====
        ('gpt-5-nano-2025-08-07', 'GPT-5 Nano (Cheap) 🚀'),
        ('gpt-5-mini-2025-08-07', 'GPT-5 Mini (Cheap) 🚀'),
        ('gpt-5-2025-08-07', 'GPT-5 (Moderate) 🚀'),
        ('gpt-5.2-2025-12-11', 'GPT-5.2 (Expensive) 🚀'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='bots',
        verbose_name='Владелец'
    )
    
    name = models.CharField(max_length=200, verbose_name='Название бота')
    description = models.TextField(blank=True, verbose_name='Описание')
    avatar = models.ImageField(upload_to='bot_avatars/', blank=True, null=True, verbose_name='Аватар')
    
    # Название компании
    company_name = models.CharField(
        max_length=100,
        default='TheCloser',
        verbose_name='Название компании',
        help_text='Название компании, от лица которой выступает бот'
    )
    
    platform = models.CharField(
        max_length=20,
        choices=PLATFORM_CHOICES,
        verbose_name='Платформа'
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='inactive',
        verbose_name='Статус'
    )
    
    # Telegram UserBot Auth Data
    phone_number = models.CharField(max_length=20, blank=True, verbose_name='Номер телефона')
    phone_code_hash = models.CharField(max_length=500, blank=True, verbose_name='Хеш кода')
    session_string = models.TextField(blank=True, null=True, verbose_name='Session String')
    api_id = models.CharField(max_length=50, null=True, blank=True, verbose_name='API ID')
    api_hash = models.CharField(max_length=100, blank=True, verbose_name='API Hash')
    
    # Токены для Bot API (Webhook)
    telegram_token = models.CharField(max_length=200, blank=True, verbose_name='Telegram Bot Token')
    whatsapp_token = models.CharField(max_length=200, blank=True, verbose_name='WhatsApp Token')
    
    # Настройки AI
    system_prompt = models.TextField(
        default='Ты - полезный AI ассистент. Отвечай четко и по существу.',
        verbose_name='Системный промпт'
    )
    
    openai_model = models.CharField(
        max_length=50,
        choices=MODEL_CHOICES,
        default='gpt-4o-mini',
        verbose_name='Модель OpenAI'
    )
    
    temperature = models.FloatField(default=0.7, verbose_name='Temperature')
    max_tokens = models.IntegerField(default=500, verbose_name='Max tokens')
    
    # Настройки RAG
    use_rag = models.BooleanField(
        default=True,
        verbose_name='Использовать базу знаний (RAG)'
    )
    
    rag_top_k = models.IntegerField(
        default=5,
        verbose_name='Количество релевантных фрагментов'
    )
    
    # Метаданные
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создан')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлен')
    
    class Meta:
        db_table = 'bot_agents'
        verbose_name = 'Бот'
        verbose_name_plural = 'Боты'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['platform']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_platform_display()})"
    
    # ========== НОВЫЙ МЕТОД: Определение типа API ==========
    def uses_new_api(self):
        """Проверяет, использует ли модель новый API (o1/o3/GPT-5+)"""
        reasoning_models = [
            'o1-mini', 'o1-2024', 'o3-mini', 'o3-2025',
            'gpt-4.1', 'gpt-5', 'gpt-5.2'
        ]
        return any(model in self.openai_model for model in reasoning_models)


# ============================================
# ОСТАЛЬНЫЕ МОДЕЛИ БЕЗ ИЗМЕНЕНИЙ
# ============================================

class Conversation(models.Model):
    """Модель диалога с пользователем"""
    
    bot = models.ForeignKey(
        BotAgent,
        on_delete=models.CASCADE,
        related_name='conversations',
        verbose_name='Бот'
    )
    
    user_id = models.CharField(
        max_length=200,
        verbose_name='ID пользователя',
        help_text='ID пользователя в мессенджере'
    )
    
    user_name = models.CharField(max_length=200, blank=True, verbose_name='Имя пользователя')
    
    is_lead = models.BooleanField(default=False, verbose_name='Лид')
    lead_email = models.EmailField(blank=True, verbose_name='Email лида')
    lead_phone = models.CharField(max_length=20, blank=True, verbose_name='Телефон лида')
    
    # ========== НОВОЕ ПОЛЕ: Динамические данные лида ==========
    lead_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Данные лида',
        help_text='Все собранные данные от клиента (имя, телефон, дата, бюджет и т.д.)'
    )
    
    started_at = models.DateTimeField(default=timezone.now, verbose_name='Начало диалога')
    last_message_at = models.DateTimeField(default=timezone.now, verbose_name='Последнее сообщение')
    
    class Meta:
        db_table = 'conversations'
        verbose_name = 'Диалог'
        verbose_name_plural = 'Диалоги'
        ordering = ['-last_message_at']
        indexes = [
            models.Index(fields=['bot', 'user_id']),
            models.Index(fields=['bot', 'is_lead']),
            models.Index(fields=['started_at']),
        ]
    
    def __str__(self):
        return f"Диалог с {self.user_name or self.user_id}"


class Message(models.Model):
    """Модель сообщения в диалоге"""
    
    ROLE_CHOICES = [
        ('user', 'Пользователь'),
        ('bot', 'Бот'),
        ('system', 'Система'),
    ]
    
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name='Диалог'
    )
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, verbose_name='Роль')
    content = models.TextField(verbose_name='Содержимое')
    
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name='Создано',
        db_index=True
    )
    
    class Meta:
        db_table = 'messages'
        verbose_name = 'Сообщение'
        verbose_name_plural = 'Сообщения'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['conversation', 'created_at']),
            models.Index(fields=['role', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.get_role_display()}: {self.content[:50]}"


class KnowledgeBase(models.Model):
    """Модель документа в базе знаний"""
    
    FILE_TYPE_CHOICES = [
        ('pdf', 'PDF'),
        ('docx', 'Word'),
        ('txt', 'Text'),
        ('md', 'Markdown'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='knowledge_files',
        verbose_name='Владелец'
    )
    
    bots = models.ManyToManyField(
        BotAgent,
        related_name='knowledge_base',
        blank=True,
        verbose_name='Боты'
    )
    
    title = models.CharField(max_length=300, verbose_name='Название')
    description = models.TextField(blank=True, verbose_name='Описание')
    
    file = models.FileField(
        upload_to=knowledge_base_upload_path,
        verbose_name='Файл'
    )
    
    file_type = models.CharField(max_length=10, choices=FILE_TYPE_CHOICES, verbose_name='Тип файла')
    file_size = models.IntegerField(default=0, verbose_name='Размер файла (байт)')
    
    is_indexed = models.BooleanField(
        default=False,
        verbose_name='Проиндексирован',
        help_text='Документ разбит на фрагменты и векторизован'
    )
    
    chunks_count = models.IntegerField(default=0, verbose_name='Количество фрагментов')
    indexed_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата индексации')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Загружен')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлен')
    
    class Meta:
        db_table = 'knowledge_base'
        verbose_name = 'Документ базы знаний'
        verbose_name_plural = 'База знаний'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_indexed']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return self.title
        
    @property
    def file_size_display(self):
        """Возвращает размер файла в человекочитаемом формате"""
        size = self.file_size
        for unit in ['Б', 'КБ', 'МБ', 'ГБ']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} ТБ"
    
    @property
    def bot_names(self):
        """Возвращает список названий ботов через запятую"""
        return ", ".join([bot.name for bot in self.bots.all()])


class KnowledgeChunk(models.Model):
    """Модель фрагмента документа с векторным представлением"""
    
    knowledge_base = models.ForeignKey(
        KnowledgeBase,
        on_delete=models.CASCADE,
        related_name='chunks',
        verbose_name='Документ'
    )
    
    text = models.TextField(verbose_name='Текст фрагмента')
    embedding = VectorField(dimensions=1536, verbose_name='Вектор')
    chunk_index = models.IntegerField(
        verbose_name='Порядковый номер',
        help_text='Порядковый номер фрагмента в документе'
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создан')
    
    class Meta:
        db_table = 'knowledge_chunks'
        verbose_name = 'Фрагмент документа'
        verbose_name_plural = 'Фрагменты документов'
        ordering = ['knowledge_base', 'chunk_index']
        indexes = [
            models.Index(fields=['knowledge_base', 'chunk_index']),
        ]
    
    def __str__(self):
        return f"Фрагмент {self.chunk_index} из {self.knowledge_base.title}"


class Analytics(models.Model):
    """Модель для хранения аналитических данных"""
    
    bot = models.ForeignKey(
        BotAgent,
        on_delete=models.CASCADE,
        related_name='analytics',
        verbose_name='Бот'
    )
    
    date = models.DateField(verbose_name='Дата', db_index=True)
    
    conversations_count = models.IntegerField(default=0, verbose_name='Количество диалогов')
    leads_count = models.IntegerField(default=0, verbose_name='Количество лидов')
    messages_count = models.IntegerField(default=0, verbose_name='Количество сообщений')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создано')
    
    class Meta:
        db_table = 'analytics'
        verbose_name = 'Аналитика'
        verbose_name_plural = 'Аналитика'
        ordering = ['-date']
        unique_together = [['bot', 'date']]
        indexes = [
            models.Index(fields=['bot', 'date']),
        ]
    
    def __str__(self):
        return f"Аналитика {self.bot.name} - {self.date}"


class CRMIntegration(models.Model):
    """Базовая модель CRM интеграции"""
    CRM_CHOICES = [
        ('bitrix24', 'Bitrix24'),
        ('amocrm', 'AmoCRM'),
        ('moysklad', 'МойСклад'),
        ('google_sheets', 'Google Sheets'),
    ]
    
    STATUS_CHOICES = [
        ('disconnected', 'Отключено'),
        ('connecting', 'Подключение...'),
        ('connected', 'Подключено'),
        ('error', 'Ошибка'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='crm_integrations')
    crm_type = models.CharField(max_length=20, choices=CRM_CHOICES, verbose_name='Тип CRM')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='disconnected', verbose_name='Статус')
    
    domain = models.CharField(max_length=255, blank=True, verbose_name='Домен/URL')
    access_token = models.TextField(blank=True, verbose_name='Access Token')
    refresh_token = models.TextField(blank=True, verbose_name='Refresh Token')
    token_expires_at = models.DateTimeField(null=True, blank=True, verbose_name='Срок действия токена')
    webhook_url = models.CharField(max_length=500, blank=True, verbose_name='Webhook URL')
    api_key = models.CharField(max_length=255, blank=True, verbose_name='API Key')
    spreadsheet_id = models.CharField(max_length=255, blank=True, verbose_name='ID таблицы')
    sheet_name = models.CharField(max_length=100, blank=True, default='Sheet1', verbose_name='Название листа')
    credentials_json = models.TextField(blank=True, verbose_name='Google Credentials JSON')
    settings = models.JSONField(default=dict, blank=True, verbose_name='Настройки')
    last_sync_at = models.DateTimeField(null=True, blank=True, verbose_name='Последняя синхронизация')
    leads_synced = models.IntegerField(default=0, verbose_name='Синхронизировано лидов')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создано')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлено')
    
    class Meta:
        db_table = 'crm_integrations'
        verbose_name = 'CRM Интеграция'
        verbose_name_plural = 'CRM Интеграции'
        unique_together = ['user', 'crm_type']
    
    def __str__(self):
        return f"{self.user.email} - {self.get_crm_type_display()}"
    
    @property
    def is_connected(self):
        return self.status == 'connected'


class CRMSyncLog(models.Model):
    """Лог синхронизации с CRM"""
    ACTION_CHOICES = [
        ('create_lead', 'Создание лида'),
        ('update_lead', 'Обновление лида'),
        ('create_contact', 'Создание контакта'),
        ('create_order', 'Создание заказа'),
        ('sync_products', 'Синхронизация товаров'),
        ('append_row', 'Добавление строки'),
        ('sync_all', 'Полная синхронизация'),
    ]
    
    STATUS_CHOICES = [
        ('success', 'Успешно'),
        ('error', 'Ошибка'),
        ('pending', 'В процессе'),
    ]
    
    integration = models.ForeignKey(CRMIntegration, on_delete=models.CASCADE, related_name='sync_logs')
    action = models.CharField(max_length=50, choices=ACTION_CHOICES, verbose_name='Действие')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='Статус')
    
    request_data = models.JSONField(default=dict, blank=True, verbose_name='Данные запроса')
    response_data = models.JSONField(default=dict, blank=True, verbose_name='Ответ')
    error_message = models.TextField(blank=True, verbose_name='Сообщение об ошибке')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создано')
    
    class Meta:
        db_table = 'crm_sync_logs'
        verbose_name = 'Лог синхронизации'
        verbose_name_plural = 'Логи синхронизации'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.integration} - {self.get_action_display()} - {self.created_at}"
    
class BotFunction(models.Model):
    """
    Гибкая модель для Function Calling
    Администратор создает функции, AI их вызывает
    """
    
    FUNCTION_TYPE_CHOICES = [
        ('save_lead', 'Сохранить лид'),
        ('call_manager', 'Позвать менеджера'),
    ]
    
    bot = models.ForeignKey(
        BotAgent,
        on_delete=models.CASCADE,
        related_name='functions',
        verbose_name='Бот'
    )
    
    # Техническое имя для AI (англ)
    name = models.CharField(
        max_length=100,
        verbose_name='Техническое имя',
        help_text='Например: save_client_info, request_human_help'
    )
    
    # Описание для AI (когда вызывать)
    description = models.TextField(
        verbose_name='Описание для AI',
        help_text='Инструкция: когда AI должен вызвать эту функцию'
    )
    
    # JSON Schema параметров
    parameters_schema = models.JSONField(
        default=dict,
        verbose_name='Схема параметров',
        help_text='JSON: какие данные должен собрать AI (имя, телефон, дата и т.д.)'
    )
    
    # Тип логики
    function_type = models.CharField(
        max_length=50,
        choices=FUNCTION_TYPE_CHOICES,
        verbose_name='Тип функции'
    )
    
    # Включена ли функция
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активна'
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создана')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлена')
    
    class Meta:
        db_table = 'bot_functions'
        verbose_name = 'Функция бота'
        verbose_name_plural = 'Функции ботов'
        ordering = ['bot', 'name']
        unique_together = ['bot', 'name']
    
    def __str__(self):
        return f"{self.bot.name} — {self.name}"
    
    def to_openai_tool(self):
        """
        Конвертирует функцию в формат OpenAI Tools API
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema
            }
        }