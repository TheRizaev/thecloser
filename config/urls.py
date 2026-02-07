# config/urls.py
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
    
    # Кастомная аутентификация (из views.py)
    path('accounts/login/', views.login_view, name='login'),
    path('accounts/logout/', views.logout_view, name='logout'),
    path('accounts/register/', views.register_view, name='register'),
    path('accounts/profile/', views.profile_view, name='profile'),

    
    # Allauth (оставляем для соц. сетей, если нужно)
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
    # Используем имена agents_*, чтобы не ломать старые шаблоны
    # ============================================
    path('dashboard/agents/', views.bots_list, name='agents_list'),
    path('dashboard/agents/create/', views.bot_create, name='create_agent'),
    path('dashboard/agents/<int:bot_id>/', views.bot_detail, name='agent_detail'),
    path('dashboard/agents/<int:bot_id>/edit/', views.bot_edit, name='bot_edit'),
    path('dashboard/agents/<int:bot_id>/delete/', views.bot_delete, name='bot_delete'),

    # API управления ботами (JS fetch)
    path('api/agents/<int:bot_id>/toggle/', views.toggle_bot_status, name='toggle_bot_status'),
    path('api/agents/<int:bot_id>/delete/', views.delete_bot_api, name='delete_bot_api'),
    path('api/agents/<int:bot_id>/update-prompt/', views.update_bot_prompt, name='update_bot_prompt'),
    path('api/agents/<int:bot_id>/update/', views.update_bot_api, name='update_bot_api'),

    # ============================================
    # TELEGRAM CONNECT (Восстановлено)
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
    # БАЗА ЗНАНИЙ (RAG)
    # ============================================
    # Список документов бота
    path('dashboard/bot/<int:bot_id>/knowledge/', views.knowledge_base_list, name='knowledge_base'),
    
    # Загрузка (Form submit)
    path('dashboard/bot/<int:bot_id>/knowledge/upload/', views.upload_knowledge_file, name='upload_kb'),
    # Загрузка (API/JS)
    path('api/agents/<int:bot_id>/upload/', views.upload_knowledge_api, name='upload_knowledge_api'),

    # Детали и удаление
    path('dashboard/knowledge/<int:kb_id>/', views.knowledge_detail, name='knowledge_detail'),
    path('dashboard/knowledge/<int:kb_id>/delete/', views.knowledge_delete, name='knowledge_delete'),
    
    # API действия с RAG
    path('api/knowledge/<int:kb_id>/reindex/', views.reindex_knowledge_base, name='reindex_kb'),
    path('api/bot/<int:bot_id>/rag/test/', views.test_rag_search, name='test_rag'),

    # ============================================
    # CRM INTEGRATIONS (views_crm)
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
    
    # Общие CRM логи
    path('dashboard/integrations/api/<str:crm_type>/status/', views_crm.get_integration_status, name='integration_status'),
    path('dashboard/integrations/api/<str:crm_type>/logs/', views_crm.get_sync_logs, name='sync_logs'),

    # ============================================
    # ANALYTICS API (Графики)
    # ============================================
    path('api/analytics/summary/', views.get_analytics_summary, name='analytics_summary'),
    path('api/analytics/conversations-chart/', views.get_conversations_chart, name='conversations_chart'),
    path('api/analytics/channels-chart/', views.get_channels_chart, name='channels_chart'),
    path('api/analytics/activity-heatmap/', views.get_activity_heatmap, name='activity_heatmap'),
    path('api/analytics/agents-performance/', views.get_agents_performance, name='agents_performance'),
    path('api/analytics/export/', views.export_analytics, name='export_analytics'),

    # Старые пути аналитики (перенаправление на новые функции, если используются)
    path('api/summary/', views.get_analytics_summary, name='analytics_summary_old'),
    path('api/conversations/', views.get_conversations_chart, name='analytics_conversations'),
    path('api/channels/', views.get_channels_chart, name='analytics_channels'),
    path('api/heatmap/', views.get_activity_heatmap, name='analytics_heatmap'),
    path('api/agents/', views.get_agents_performance, name='analytics_agents'),

    # ============================================
    # WEBHOOKS & BOT API
    # ============================================
    path('api/webhook/telegram/<str:bot_token>/', views.telegram_webhook, name='telegram_webhook'),
    path('api/webhook/whatsapp/<str:bot_token>/', views.whatsapp_webhook, name='whatsapp_webhook'),
    path('api/bot/<int:bot_id>/send/', views.send_message_api, name='send_message_api'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)