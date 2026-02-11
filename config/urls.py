# config/urls.py
"""
URL Configuration - ОЧИЩЕНО И ОПТИМИЗИРОВАНО
Убраны дублирующиеся и неиспользуемые пути
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core import views, views_crm

urlpatterns = [
    # ============================================
    # ADMIN & AUTH
    # ============================================
    path('admin/', admin.site.urls),
    
    # Кастомная аутентификация
    path('accounts/login/', views.login_view, name='login'),
    path('accounts/logout/', views.logout_view, name='logout'),
    path('accounts/register/', views.register_view, name='register'),
    path('accounts/profile/', views.profile_view, name='profile'),
    
    # Allauth (для социальных сетей)
    path('accounts/', include('allauth.urls')),
    
    # ============================================
    # PUBLIC PAGES
    # ============================================
    path('', views.home, name='home'),
    path('pricing/', views.pricing, name='pricing'),
    path('templates/', views.templates_view, name='templates'),
    path('docs/', views.docs, name='docs'),

    # ============================================
    # DASHBOARD
    # ============================================
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/settings/', views.settings_view, name='settings'),
    path('dashboard/analytics/', views.analytics_view, name='analytics'),

    # ============================================
    # БОТЫ (AGENTS)
    # ============================================
    path('dashboard/agents/', views.bots_list, name='agents_list'),
    path('dashboard/agents/create/', views.bot_create, name='create_agent'),
    path('dashboard/agents/<int:bot_id>/', views.bot_detail, name='agent_detail'),
    path('dashboard/agents/<int:bot_id>/test-chat/', views.bot_test_chat, name='bot_test_chat'),
    
    # API управления ботами
    path('api/agents/<int:bot_id>/toggle/', views.toggle_bot_status, name='toggle_bot_status'),
    path('api/agents/<int:bot_id>/delete/', views.delete_bot_api, name='delete_bot_api'),
    path('api/agents/<int:bot_id>/update-prompt/', views.update_bot_prompt, name='update_bot_prompt'),
    path('api/agents/<int:bot_id>/update/', views.update_bot_api, name='update_bot_api'),
    
    
    path('api/agents/<int:bot_id>/functions/create/', views.create_function, name='create_function'),
    path('api/agents/<int:bot_id>/functions/<int:function_id>/', views.get_function, name='get_function'),
    path('api/agents/<int:bot_id>/functions/<int:function_id>/update/', views.update_function, name='update_function'),
    path('api/agents/<int:bot_id>/functions/<int:function_id>/toggle/', views.toggle_function, name='toggle_function'),
    path('api/agents/<int:bot_id>/functions/<int:function_id>/delete/', views.delete_function, name='delete_function'),

    # ============================================
    # TELEGRAM CONNECT
    # ============================================
    path('dashboard/agents/<int:bot_id>/telegram-connect/', views.telegram_connect_view, name='telegram_connect'),
    path('api/agents/<int:bot_id>/telegram/save-credentials/', views.telegram_save_credentials, name='telegram_save_credentials'),
    path('api/agents/<int:bot_id>/telegram/send-code/', views.telegram_send_code, name='telegram_send_code'),
    path('api/agents/<int:bot_id>/telegram/verify-code/', views.telegram_verify_code, name='telegram_verify_code'),
    path('api/agents/<int:bot_id>/telegram/validate-session/', views.telegram_validate_session, name='telegram_validate_session'),
    path('api/agents/<int:bot_id>/telegram/account-info/', views.telegram_get_account_info, name='telegram_account_info'),
    path('api/agents/<int:bot_id>/telegram/disconnect/', views.telegram_disconnect, name='telegram_disconnect'),

    # ============================================
    # ДИАЛОГИ (CONVERSATIONS)
    # ============================================
    path('dashboard/conversations/', views.conversations_list, name='conversations_list'),
    path('dashboard/conversations/<int:conversation_id>/', views.conversation_detail, name='conversation_detail'),

    # ============================================
    # БАЗА ЗНАНИЙ (RAG) - ОБНОВЛЕНО!
    # ============================================
    # Общая база знаний пользователя (все файлы)
    path('dashboard/knowledge/', views.knowledge_base_list, name='knowledge_base_list'),
    
    # База знаний конкретного бота (отфильтрованная)
    path('dashboard/agents/<int:bot_id>/knowledge/', views.bot_knowledge_base, name='bot_knowledge_base'),
    
    # Загрузка файлов
    path('dashboard/knowledge/upload/', views.upload_knowledge_file, name='upload_knowledge'),
    
    # Детали и удаление
    path('dashboard/knowledge/<int:kb_id>/', views.knowledge_detail, name='knowledge_detail'),
    path('dashboard/knowledge/<int:kb_id>/delete/', views.knowledge_delete, name='knowledge_delete'),
    
    # Назначение ботов к файлу
    path('api/knowledge/<int:kb_id>/assign-bots/', views.assign_bots_to_knowledge, name='assign_bots'),
    
    # API действия с RAG
    path('api/knowledge/<int:kb_id>/reindex/', views.reindex_knowledge_base, name='reindex_kb'),
    path('api/bot/<int:bot_id>/rag/test/', views.test_rag_search, name='test_rag'),

    # ============================================
    # CRM INTEGRATIONS
    # ============================================
    path('dashboard/integrations/', views_crm.integrations_view, name='integrations'),
    
    # Bitrix24
    path('dashboard/integrations/api/bitrix24/connect/', views_crm.connect_bitrix24, name='connect_bitrix24'),
    path('dashboard/integrations/api/bitrix24/disconnect/', views_crm.disconnect_bitrix24, name='disconnect_bitrix24'),
    path('dashboard/integrations/api/bitrix24/test/', views_crm.test_bitrix24, name='test_bitrix24'),
    
    # AmoCRM
    path('dashboard/integrations/api/amocrm/connect/', views_crm.connect_amocrm, name='connect_amocrm'),
    path('dashboard/integrations/api/amocrm/connect-simple/', views_crm.connect_amocrm_simple, name='connect_amocrm_simple'),
    path('dashboard/integrations/api/amocrm/disconnect/', views_crm.disconnect_amocrm, name='disconnect_amocrm'),
    
    # МойСклад
    path('dashboard/integrations/api/moysklad/connect/', views_crm.connect_moysklad, name='connect_moysklad'),
    path('dashboard/integrations/api/moysklad/connect-token/', views_crm.connect_moysklad_token, name='connect_moysklad_token'),
    path('dashboard/integrations/api/moysklad/disconnect/', views_crm.disconnect_moysklad, name='disconnect_moysklad'),
    path('dashboard/integrations/api/moysklad/test/', views_crm.test_moysklad, name='test_moysklad'),
    
    # Google Sheets
    path('dashboard/integrations/api/google-sheets/connect/', views_crm.connect_google_sheets, name='connect_google_sheets'),
    path('dashboard/integrations/api/google-sheets/connect-simple/', views_crm.connect_google_sheets_simple, name='connect_google_sheets_simple'),
    path('dashboard/integrations/api/google-sheets/disconnect/', views_crm.disconnect_google_sheets, name='disconnect_google_sheets'),
    path('dashboard/integrations/api/google-sheets/test/', views_crm.test_google_sheets, name='test_google_sheets'),

    # ============================================
    # ANALYTICS API
    # ============================================
    path('api/analytics/summary/', views.get_analytics_summary, name='analytics_summary'),
    path('api/analytics/conversations-chart/', views.get_conversations_chart, name='conversations_chart'),
    path('api/analytics/channels-chart/', views.get_channels_chart, name='channels_chart'),
    path('api/analytics/activity-heatmap/', views.get_activity_heatmap, name='activity_heatmap'),
    path('api/analytics/agents-performance/', views.get_agents_performance, name='agents_performance'),
    path('api/analytics/export/', views.export_analytics, name='export_analytics'),

    # ============================================
    # WEBHOOKS
    # ============================================
    path('api/webhook/telegram/<str:bot_token>/', views.telegram_webhook, name='telegram_webhook'),
    path('api/webhook/whatsapp/<str:bot_token>/', views.whatsapp_webhook, name='whatsapp_webhook'),
    path('api/bot/<int:bot_id>/send/', views.send_message_api, name='send_message_api'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)