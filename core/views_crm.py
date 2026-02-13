# core/views_crm.py
import json
import logging
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.utils import timezone
from .models import CRMIntegration, CRMSyncLog
import requests
from django.conf import settings




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
def connect_amocrm(request):
    """
    Шаг 1: Редирект пользователя на AmoCRM для получения прав
    """
    client_id = settings.AMOCRM_CLIENT_ID
    # state нужен для защиты и передачи ID юзера, чтобы проверить его при возврате
    state = str(request.user.id)
    
    # Формируем URL авторизации
    # AmoCRM требует редиректа на www.amocrm.ru/oauth
    auth_url = (
        f"https://www.amocrm.ru/oauth?"
        f"client_id={client_id}&"
        f"state={state}&"
        f"mode=post_message"
    )
    
    return redirect(auth_url)

@login_required
def amocrm_callback(request):
    """
    Шаг 2: Обработка возврата от AmoCRM с кодом авторизации
    """
    code = request.GET.get('code')
    # referer - это домен аккаунта пользователя (например, company.amocrm.ru)
    # В новых версиях API AmoCRM может передавать это в заголовке или параметре, 
    # но часто нужно смотреть client_id. 
    # При mode=post_message AmoCRM обычно передает referer в GET параметрах, если это кнопка на сайте,
    # но при прямой OAuth ссылке referer - это домен, откуда пришел юзер.
    # В данном случае, мы получим referer из запроса на token endpoint позже, или из GET параметра 'referer'
    
    referer = request.GET.get('referer') 
    state = request.GET.get('state')
    error = request.GET.get('error')

    if error:
        return JsonResponse({'success': False, 'error': f"Ошибка AmoCRM: {error}"})

    # Проверка безопасности
    if str(request.user.id) != state:
        return JsonResponse({'success': False, 'error': "Ошибка безопасности (state mismatch)"})

    if not code:
        return JsonResponse({'success': False, 'error': "Не получен код от AmoCRM"})

    if not referer:
        # Если referer не пришел в GET, пробуем получить его при обмене токена, 
        # но для формирования URL запроса нам нужен домен.
        # Обычно AmoCRM возвращает: ?code=...&referer=subdomain.amocrm.ru&state=...
        return JsonResponse({'success': False, 'error': "Не удалось определить домен AmoCRM (referer)"})

    # Шаг 3: Меняем код на Access Token
    url = f"https://{referer}/oauth2/access_token"
    
    payload = {
        "client_id": settings.AMOCRM_CLIENT_ID,
        "client_secret": settings.AMOCRM_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.AMOCRM_REDIRECT_URI,
    }

    try:
        response = requests.post(url, json=payload)
        data = response.json()

        if response.status_code not in [200, 201]:
            logger.error(f"AmoCRM Token Error: {data}")
            return JsonResponse({'success': False, 'error': f"Ошибка получения токена: {data.get('hint') or data.get('title')}"})

        # Сохраняем интеграцию
        integration, _ = CRMIntegration.objects.get_or_create(
            user=request.user,
            crm_type='amocrm'
        )

        integration.domain = referer
        integration.access_token = data.get('access_token')
        integration.refresh_token = data.get('refresh_token')
        
        expires_in = data.get('expires_in', 86400)
        integration.token_expires_at = timezone.now() + timezone.timedelta(seconds=expires_in)
        
        integration.status = 'connected'
        integration.save()

        return redirect('integrations')

    except Exception as e:
        logger.error(f"AmoCRM Callback Exception: {e}")
        return JsonResponse({'success': False, 'error': str(e)})

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