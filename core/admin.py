from django.contrib import admin
from .models import (
    BotAgent, 
    Conversation, 
    Message, 
    KnowledgeBase, 
    KnowledgeChunk,
    Analytics,
    CRMIntegration
)


@admin.register(BotAgent)
class BotAgentAdmin(admin.ModelAdmin):
    list_display = ('name', 'platform', 'user', 'created_at')
    list_filter = ('platform', 'created_at')
    search_fields = ('name', 'description', 'user__email')
    

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'bot', 'user_id', 'user_name')
    list_filter = ('bot',)
    search_fields = ('user_id', 'user_name')


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'role', 'content_preview')
    list_filter = ('role',)
    search_fields = ('content',)
    
    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Содержимое'


@admin.register(KnowledgeBase)
class KnowledgeBaseAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'get_bots_display', 'file_type', 'is_indexed', 'created_at')
    list_filter = ('file_type', 'is_indexed', 'created_at')
    search_fields = ('title', 'description', 'user__email')
    filter_horizontal = ('bots',)
    
    def get_bots_display(self, obj):
        bots = obj.bots.all()[:3]
        names = [bot.name for bot in bots]
        result = ", ".join(names)
        if obj.bots.count() > 3:
            result += f" (+{obj.bots.count() - 3})"
        return result or "Не назначено"
    get_bots_display.short_description = 'Боты'


@admin.register(KnowledgeChunk)
class KnowledgeChunkAdmin(admin.ModelAdmin):
    list_display = ('id', 'knowledge_base', 'chunk_index', 'text_preview', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('text',)
    
    def text_preview(self, obj):
        return obj.text[:100] + '...' if len(obj.text) > 100 else obj.text
    text_preview.short_description = 'Текст (превью)'


@admin.register(Analytics)
class AnalyticsAdmin(admin.ModelAdmin):
    list_display = ('bot', 'date')
    list_filter = ('date', 'bot')
    search_fields = ('bot__name',)
    date_hierarchy = 'date'


@admin.register(CRMIntegration)
class CRMIntegrationAdmin(admin.ModelAdmin):
    list_display = ('id', 'crm_type', 'created_at')
    list_filter = ('crm_type', 'created_at')
    search_fields = ('crm_type',)