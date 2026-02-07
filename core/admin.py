# core/admin.py
"""
Административная панель Django для SalesAI
"""

from django.contrib import admin
from .models import BotAgent, Conversation, Message, KnowledgeBase, KnowledgeChunk, Analytics


@admin.register(BotAgent)
class BotAgentAdmin(admin.ModelAdmin):
    """Админка для ботов"""
    list_display = ['name', 'user', 'platform', 'status', 'use_rag', 'created_at']
    list_filter = ['platform', 'status', 'use_rag', 'created_at']
    search_fields = ['name', 'user__username', 'description']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('user', 'name', 'description', 'platform', 'status')
        }),
        ('Токены интеграций', {
            'fields': ('telegram_token', 'whatsapp_token'),
            'classes': ('collapse',)
        }),
        ('Настройки AI', {
            'fields': ('system_prompt', 'openai_model', 'temperature', 'max_tokens')
        }),
        ('Настройки RAG', {
            'fields': ('use_rag', 'rag_top_k')
        }),
        ('Метаданные', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    """Админка для диалогов"""
    list_display = ['id', 'bot', 'user_name', 'user_id', 'is_lead', 'started_at', 'last_message_at']
    list_filter = ['bot', 'is_lead', 'started_at']
    search_fields = ['user_name', 'user_id', 'lead_email']
    readonly_fields = ['started_at']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('bot', 'user_id', 'user_name')
        }),
        ('Информация о лиде', {
            'fields': ('is_lead', 'lead_email', 'lead_phone')
        }),
        ('Временные метки', {
            'fields': ('started_at', 'last_message_at')
        }),
    )


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    """Админка для сообщений"""
    list_display = ['id', 'conversation', 'role', 'content_preview', 'created_at']
    list_filter = ['role', 'created_at']
    search_fields = ['content', 'conversation__user_name']
    readonly_fields = ['created_at']
    
    def content_preview(self, obj):
        """Превью содержимого"""
        return obj.content[:100] + '...' if len(obj.content) > 100 else obj.content
    content_preview.short_description = 'Содержимое'


@admin.register(KnowledgeBase)
class KnowledgeBaseAdmin(admin.ModelAdmin):
    """Админка для базы знаний"""
    list_display = ['title', 'bot', 'file_type', 'is_indexed', 'chunks_count', 'created_at']
    list_filter = ['file_type', 'is_indexed', 'created_at']
    search_fields = ['title', 'description', 'bot__name']
    readonly_fields = ['file_size', 'is_indexed', 'chunks_count', 'indexed_at', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('bot', 'title', 'description')
        }),
        ('Файл', {
            'fields': ('file', 'file_type', 'file_size')
        }),
        ('Индексация', {
            'fields': ('is_indexed', 'chunks_count', 'indexed_at')
        }),
        ('Метаданные', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(KnowledgeChunk)
class KnowledgeChunkAdmin(admin.ModelAdmin):
    """Админка для фрагментов документов"""
    list_display = ['id', 'knowledge_base', 'chunk_index', 'text_preview', 'created_at']
    list_filter = ['created_at']
    search_fields = ['text', 'knowledge_base__title']
    readonly_fields = ['created_at']
    
    def text_preview(self, obj):
        """Превью текста"""
        return obj.text[:100] + '...' if len(obj.text) > 100 else obj.text
    text_preview.short_description = 'Текст'
    
    # Не показываем embedding в форме (слишком большой)
    exclude = ['embedding']


@admin.register(Analytics)
class AnalyticsAdmin(admin.ModelAdmin):
    """Админка для аналитики"""
    list_display = ['bot', 'date', 'conversations_count', 'leads_count', 'messages_count']
    list_filter = ['date', 'bot']
    search_fields = ['bot__name']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('bot', 'date')
        }),
        ('Метрики', {
            'fields': ('conversations_count', 'leads_count', 'messages_count')
        }),
        ('Метаданные', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )


# Настройки админки
admin.site.site_header = 'SalesAI Администрирование'
admin.site.site_title = 'SalesAI Admin'
admin.site.index_title = 'Управление системой'