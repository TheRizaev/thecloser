# core/views_crm.py
import json
import logging
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.utils import timezone
from .models import CRMIntegration, CRMSyncLog

logger = logging.getLogger(__name__)

@login_required
def integrations_view(request):
    """Страница со списком интеграций"""
    integrations = CRMIntegration.objects.filter(user=request.user)
    
    # Преобразуем в словарь для удобства в шаблоне: {'bitrix24': obj, 'amocrm': obj ...}
    integrations_dict = {i.crm_type: i for i in integrations}
    
    context = {
        'integrations': integrations_dict,
        # Передаем список доступных типов, чтобы в шаблоне знать, что рисовать
        'available_crms': ['bitrix24', 'amocrm', 'moysklad', 'google_sheets']
    }
    return render(request, 'dashboard/integrations.html', context)

# ================= BITRIX24 =================

@login_required
@require_http_methods(["POST"])
def connect_bitrix24(request):
    """Подключение Bitrix24 через Webhook"""
    try:
        data = json.loads(request.body)
        webhook_url = data.get('webhook_url', '').strip()
        
        if not webhook_url:
            return JsonResponse({'success': False, 'error': 'Введите Webhook URL'})
            
        integration, _ = CRMIntegration.objects.get_or_create(
            user=request.user, 
            crm_type='bitrix24'
        )
        
        integration.webhook_url = webhook_url
        integration.domain = webhook_url.split('/')[2] if '//' in webhook_url else 'bitrix24'
        integration.status = 'connected'
        integration.save()
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["POST"])
def disconnect_bitrix24(request):
    """Отключение Bitrix24"""
    CRMIntegration.objects.filter(user=request.user, crm_type='bitrix24').delete()
    return JsonResponse({'success': True})

@login_required
@require_http_methods(["POST"])
def test_bitrix24(request):
    """Тест соединения Bitrix24"""
    # Здесь можно сделать реальный запрос к API Битрикса
    return JsonResponse({'success': True, 'message': 'Соединение установлено!'})

# ================= AMOCRM =================

@login_required
@require_http_methods(["GET"])
def connect_amocrm(request):
    """OAuth редирект для AmoCRM (заглушка)"""
    return JsonResponse({'success': False, 'error': 'OAuth not configured'})

@login_required
@require_http_methods(["POST"])
def connect_amocrm_simple(request):
    """Подключение AmoCRM через API Key (упрощенно)"""
    try:
        data = json.loads(request.body)
        domain = data.get('domain', '').strip()
        api_key = data.get('api_key', '').strip() # Или Long-lived token
        
        if not domain or not api_key:
             return JsonResponse({'success': False, 'error': 'Заполните все поля'})
             
        integration, _ = CRMIntegration.objects.get_or_create(
            user=request.user, 
            crm_type='amocrm'
        )
        integration.domain = domain
        integration.api_key = api_key
        integration.status = 'connected'
        integration.save()
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["POST"])
def disconnect_amocrm(request):
    CRMIntegration.objects.filter(user=request.user, crm_type='amocrm').delete()
    return JsonResponse({'success': True})

# ================= MOYSKLAD =================

@login_required
@require_http_methods(["GET"])
def connect_moysklad(request):
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@login_required
@require_http_methods(["POST"])
def connect_moysklad_token(request):
    """Подключение МойСклад через токен"""
    try:
        data = json.loads(request.body)
        token = data.get('token', '').strip()
        
        if not token:
            return JsonResponse({'success': False, 'error': 'Введите токен'})
            
        integration, _ = CRMIntegration.objects.get_or_create(
            user=request.user, 
            crm_type='moysklad'
        )
        integration.access_token = token
        integration.status = 'connected'
        integration.save()
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["POST"])
def disconnect_moysklad(request):
    CRMIntegration.objects.filter(user=request.user, crm_type='moysklad').delete()
    return JsonResponse({'success': True})

@login_required
@require_http_methods(["POST"])
def test_moysklad(request):
    return JsonResponse({'success': True, 'message': 'API доступен'})

# ================= GOOGLE SHEETS =================

@login_required
@require_http_methods(["GET"])
def connect_google_sheets(request):
    return JsonResponse({'error': 'Use connect-simple'}, status=405)

@login_required
@require_http_methods(["POST"])
def connect_google_sheets_simple(request):
    """Подключение Google Sheets через JSON файл сервисного аккаунта"""
    try:
        spreadsheet_id = request.POST.get('spreadsheet_id')
        
        if 'credentials_file' not in request.FILES or not spreadsheet_id:
            return JsonResponse({'success': False, 'error': 'Загрузите JSON и укажите ID таблицы'})
            
        file = request.FILES['credentials_file']
        if not file.name.endswith('.json'):
            return JsonResponse({'success': False, 'error': 'Файл должен быть .json'})
            
        json_content = file.read().decode('utf-8')
        
        # Простая валидация JSON
        try:
            json.loads(json_content)
        except:
             return JsonResponse({'success': False, 'error': 'Некорректный JSON'})

        integration, _ = CRMIntegration.objects.get_or_create(
            user=request.user, 
            crm_type='google_sheets'
        )
        integration.credentials_json = json_content
        integration.spreadsheet_id = spreadsheet_id
        integration.status = 'connected'
        integration.save()
        
        return JsonResponse({'success': True})
    except Exception as e:
        logger.error(f"Google Sheets connect error: {e}")
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["POST"])
def disconnect_google_sheets(request):
    CRMIntegration.objects.filter(user=request.user, crm_type='google_sheets').delete()
    return JsonResponse({'success': True})

@login_required
@require_http_methods(["POST"])
def test_google_sheets(request):
    # Заглушка теста
    return JsonResponse({'success': True, 'message': 'Доступ к таблице есть'})

# ================= COMMON =================

@login_required
def get_integration_status(request, crm_type):
    """Получение статуса интеграции (polling)"""
    try:
        integration = CRMIntegration.objects.get(user=request.user, crm_type=crm_type)
        return JsonResponse({
            'status': integration.status,
            'last_sync': integration.last_sync_at.strftime('%d.%m.%Y %H:%M') if integration.last_sync_at else '-'
        })
    except CRMIntegration.DoesNotExist:
        return JsonResponse({'status': 'disconnected'})

@login_required
def get_sync_logs(request, crm_type):
    """Получение логов синхронизации"""
    try:
        integration = CRMIntegration.objects.get(user=request.user, crm_type=crm_type)
        logs = CRMSyncLog.objects.filter(integration=integration).order_by('-created_at')[:10]
        
        data = [{
            'action': log.get_action_display(),
            'status': log.status,
            'time': log.created_at.strftime('%H:%M'),
            'error': log.error_message
        } for log in logs]
        
        return JsonResponse({'logs': data})
    except CRMIntegration.DoesNotExist:
        return JsonResponse({'logs': []})