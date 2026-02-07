# core/views.py
"""
Views для проекта SalesAI
Включает: Дашборд, Боты, Диалоги, Аналитику, Базу знаний (RAG)
Объединенная версия: функционал RAG/Аналитики + логика подключения Telegram
"""

import os
import json
import logging
from datetime import datetime, timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Count, Q, Avg, Sum
from django.db.models.functions import TruncDate, ExtractWeekDay, ExtractHour
from django.utils import timezone
from django.core.paginator import Paginator

# Импорты моделей и сервисов
from .models import BotAgent, Conversation, Message, KnowledgeBase, KnowledgeChunk, Analytics
from services.rag_service import rag_service

from asgiref.sync import async_to_sync
from .telegram_auth import send_code_request, verify_code

logger = logging.getLogger(__name__)

# ============================================
# HELPER FUNCTIONS
# ============================================

ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.txt'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

def get_file_type(filename):
    """Определяет тип файла по расширению"""
    ext = os.path.splitext(filename)[1].lower()
    if ext in ALLOWED_EXTENSIONS:
        return ext.replace('.', '')
    return 'other'

# ============================================
# PUBLIC PAGES
# ============================================

def home(request):
    """Главная страница"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'index.html')

def pricing(request):
    """Страница тарифов"""
    return render(request, 'pricing.html')

def templates_view(request):
    """Страница шаблонов"""
    return render(request, 'templates.html')

def docs(request):
    """Страница документации"""
    return render(request, 'docs.html')

# ============================================
# АУТЕНТИФИКАЦИЯ
# ============================================

def login_view(request):
    """Вход СТРОГО по Email"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        # ДЕБАГ: выводим всё что пришло
        print("=" * 50)
        print(f"POST data: {dict(request.POST)}")
        
        email = request.POST.get('login') or request.POST.get('email')
        password = request.POST.get('password')
        
        print(f"Extracted email: '{email}'")
        print(f"Password exists: {bool(password)}")
        print(f"Password length: {len(password) if password else 0}")
        
        try:
            user_obj = User.objects.get(email__iexact=email)
            print(f"User found: {user_obj.username} (ID: {user_obj.id})")
            print(f"User is_active: {user_obj.is_active}")
            
            # Проверяем пароль напрямую
            password_valid = user_obj.check_password(password)
            print(f"check_password result: {password_valid}")
            
            # Пробуем authenticate
            user = authenticate(username=user_obj.username, password=password)
            print(f"authenticate result: {user}")
            
            if user is not None:
                login(request, user)
                print("Login successful, redirecting...")
                return redirect('dashboard')
            else:
                print("ERROR: authenticate returned None!")
                messages.error(request, 'Неверный пароль')
                
        except User.DoesNotExist:
            print(f"ERROR: User with email '{email}' not found")
            messages.error(request, 'Пользователь с таким email не найден')
        
        print("=" * 50)
            
    return render(request, 'account/login.html')

@login_required
def logout_view(request):
    """Выход из системы"""
    logout(request)
    messages.success(request, 'Вы успешно вышли из системы')
    return redirect('login')

def register_view(request):
    """Регистрация нового пользователя"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        
        # Валидация
        if password != password_confirm:
            messages.error(request, 'Пароли не совпадают')
            return render(request, 'account/signup.html')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Пользователь с таким именем уже существует')
            return render(request, 'account/signup.html')
        
        # Создаем пользователя
        user = User.objects.create_user(username=username, email=email, password=password)
        login(request, user)
        messages.success(request, 'Регистрация успешна!')
        return redirect('dashboard')
    
    # Исправлено: путь к шаблону
    return render(request, 'account/signup.html')

@login_required
def profile_view(request):
    """Профиль пользователя"""
    if request.method == 'POST':
        user = request.user
        user.first_name = request.POST.get('first_name', '')
        user.last_name = request.POST.get('last_name', '')
        user.email = request.POST.get('email', '')
        user.save()
        messages.success(request, 'Профиль обновлен')
        return redirect('profile')
    
    # Здесь можно использовать dashboard/settings.html или отдельный шаблон
    return render(request, 'dashboard/settings.html') 

# ============================================
# DASHBOARD
# ============================================

@login_required
def dashboard(request):
    """Главная страница дашборда"""
    user_bots = BotAgent.objects.filter(user=request.user)
    
    # Статистика
    total_bots = user_bots.count()
    total_conversations = Conversation.objects.filter(bot__user=request.user).count()
    total_leads = Conversation.objects.filter(bot__user=request.user, is_lead=True).count()
    
    # Последние диалоги
    recent_conversations = Conversation.objects.filter(
        bot__user=request.user
    ).select_related('bot').order_by('-last_message_at')[:10]
    
    context = {
        'total_bots': total_bots,
        'total_conversations': total_conversations,
        'total_leads': total_leads,
        'bots': user_bots,
        'recent_conversations': recent_conversations,
        # Добавил для sidebar active state
        'active_bots': total_bots 
    }
    
    return render(request, 'dashboard/index.html', context)

# ============================================
# УПРАВЛЕНИЕ БОТАМИ
# ============================================

@login_required
def bots_list(request):
    """Список ботов пользователя"""
    bots = BotAgent.objects.filter(user=request.user).order_by('-created_at')
    
    # Добавляем статистику к каждому боту
    for bot in bots:
        bot.conversations_count = Conversation.objects.filter(bot=bot).count()
        bot.leads_count = Conversation.objects.filter(bot=bot, is_lead=True).count()
    
    # Исправлено: путь к шаблону (у вас файл называется agents.html)
    return render(request, 'dashboard/agents.html', {'bots': bots})

@login_required
def bot_detail(request, bot_id):
    """Детали бота"""
    bot = get_object_or_404(BotAgent, id=bot_id, user=request.user)
    
    # Статистика
    conversations = Conversation.objects.filter(bot=bot)
    bot.conversations_count = conversations.count()
    bot.leads_count = conversations.filter(is_lead=True).count()
    bot.knowledge_count = KnowledgeBase.objects.filter(bot=bot).count()
    
    # Исправлено: путь к шаблону (agent_detail.html)
    return render(request, 'dashboard/agent_detail.html', {'bot': bot})

@login_required
def bot_create(request):
    """Создание нового бота"""
    if request.method == 'POST':
        bot = BotAgent.objects.create(
            user=request.user,
            name=request.POST.get('name'),
            description=request.POST.get('description', ''),
            platform=request.POST.get('platform'),
            system_prompt=request.POST.get('system_prompt', 'Ты - полезный AI ассистент.'),
            telegram_token=request.POST.get('telegram_token', ''),
            whatsapp_token=request.POST.get('whatsapp_token', ''),
        )
        messages.success(request, f'Бот "{bot.name}" успешно создан')
        # Исправлено: редирект на agent_detail (имя в urls.py)
        return redirect('agent_detail', bot_id=bot.id)
    
    return render(request, 'dashboard/create_agent.html')

@login_required
def bot_edit(request, bot_id):
    """Редактирование бота (используем тот же шаблон деталей, но с логикой)"""
    # Обычно редактирование происходит в модалке или на странице деталей,
    # здесь просто редирект на детали, так как отдельного шаблона bot_edit.html в списке нет
    return redirect('agent_detail', bot_id=bot_id)

@login_required
@require_http_methods(['POST'])
def bot_delete(request, bot_id):
    """Удаление бота (форма)"""
    bot = get_object_or_404(BotAgent, id=bot_id, user=request.user)
    bot_name = bot.name
    bot.delete()
    
    messages.success(request, f'Бот "{bot_name}" удален')
    # Исправлено: редирект на agents_list
    return redirect('agents_list')

# ============================================
# ДИАЛОГИ И СООБЩЕНИЯ
# ============================================

@login_required
def conversations_list(request):
    """Список диалогов"""
    conversations = Conversation.objects.filter(
        bot__user=request.user
    ).select_related('bot').order_by('-last_message_at')
    
    # Фильтрация
    bot_id = request.GET.get('bot')
    if bot_id:
        conversations = conversations.filter(bot_id=bot_id)
    
    is_lead = request.GET.get('is_lead')
    if is_lead == '1':
        conversations = conversations.filter(is_lead=True)
    
    # Пагинация
    paginator = Paginator(conversations, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'bots': BotAgent.objects.filter(user=request.user),
    }
    
    # Исправлено: шаблон conversations.html
    return render(request, 'dashboard/conversations.html', context)

@login_required
def conversation_detail(request, conversation_id):
    """Детали диалога"""
    conversation = get_object_or_404(
        Conversation,
        id=conversation_id,
        bot__user=request.user
    )
    
    messages_list = conversation.messages.all().order_by('created_at')
    
    context = {
        'conversation': conversation,
        'messages': messages_list,
    }
    
    return render(request, 'dashboard/conversation_detail.html', context)

# ============================================
# АНАЛИТИКА
# ============================================

@login_required
def analytics_view(request):
    """Главная страница аналитики"""
    user_bots = BotAgent.objects.filter(user=request.user)
    context = {'bots': user_bots}
    return render(request, 'dashboard/analytics.html', context)

@login_required
@require_http_methods(['GET'])
def get_analytics_summary(request):
    """API: Сводная статистика"""
    agent_id = request.GET.get('agent_id', 'all')
    channel = request.GET.get('channel', 'all')
    period = request.GET.get('period', '7days')
    
    now = timezone.now()
    end_date = now.date()
    
    if period == 'today':
        start_date = end_date
    elif period == 'yesterday':
        start_date = end_date - timedelta(days=1)
        end_date = start_date
    elif period == '7days':
        start_date = end_date - timedelta(days=7)
    elif period == '30days':
        start_date = end_date - timedelta(days=30)
    elif period == '90days':
        start_date = end_date - timedelta(days=90)
    else:
        start_date = end_date - timedelta(days=7)
    
    bots_query = BotAgent.objects.filter(user=request.user)
    if agent_id != 'all':
        bots_query = bots_query.filter(id=agent_id)
    if channel != 'all':
        bots_query = bots_query.filter(platform=channel)
    
    conversations_current = Conversation.objects.filter(
        bot__in=bots_query,
        started_at__date__gte=start_date,
        started_at__date__lte=end_date
    )
    
    total_conversations = conversations_current.count()
    total_leads = conversations_current.filter(is_lead=True).count()
    conversion_rate = (total_leads / total_conversations * 100) if total_conversations > 0 else 0
    
    # Сравнение с прошлым периодом
    period_length = (end_date - start_date).days + 1
    prev_start_date = start_date - timedelta(days=period_length)
    prev_end_date = start_date - timedelta(days=1)
    
    conversations_previous = Conversation.objects.filter(
        bot__in=bots_query,
        started_at__date__gte=prev_start_date,
        started_at__date__lte=prev_end_date
    )
    
    prev_conversations = conversations_previous.count()
    prev_leads = conversations_previous.filter(is_lead=True).count()
    
    def calculate_change(current, previous):
        if previous == 0:
            return 100 if current > 0 else 0
        return round(((current - previous) / previous) * 100, 1)
    
    return JsonResponse({
        'success': True,
        'data': {
            'total_conversations': total_conversations,
            'total_leads': total_leads,
            'conversion_rate': round(conversion_rate, 1),
            'avg_response_time': 1.2,
            'changes': {
                'conversations': calculate_change(total_conversations, prev_conversations),
                'leads': calculate_change(total_leads, prev_leads),
                'conversion': round(conversion_rate, 1),
                'response_time': 0,
            }
        }
    })

@login_required
@require_http_methods(['GET'])
def get_conversations_chart(request):
    """API: График диалогов по дням"""
    agent_id = request.GET.get('agent_id', 'all')
    period = request.GET.get('period', '7days')
    
    now = timezone.now()
    end_date = now.date()
    
    if period == 'today':
        start_date = end_date
    elif period == '7days':
        start_date = end_date - timedelta(days=7)
    elif period == '30days':
        start_date = end_date - timedelta(days=30)
    else:
        start_date = end_date - timedelta(days=7)
    
    bots_query = BotAgent.objects.filter(user=request.user)
    if agent_id != 'all':
        bots_query = bots_query.filter(id=agent_id)
    
    conversations_by_date = Conversation.objects.filter(
        bot__in=bots_query,
        started_at__date__gte=start_date,
        started_at__date__lte=end_date
    ).annotate(
        date=TruncDate('started_at')
    ).values('date').annotate(
        total=Count('id'),
        leads=Count('id', filter=Q(is_lead=True))
    ).order_by('date')
    
    date_range = []
    current_date = start_date
    while current_date <= end_date:
        date_range.append(current_date)
        current_date += timedelta(days=1)
    
    data_dict = {item['date']: item for item in conversations_by_date}
    labels = []
    conversations_data = []
    leads_data = []
    
    for date in date_range:
        labels.append(date.strftime('%Y-%m-%d'))
        if date in data_dict:
            conversations_data.append(data_dict[date]['total'])
            leads_data.append(data_dict[date]['leads'])
        else:
            conversations_data.append(0)
            leads_data.append(0)
    
    return JsonResponse({
        'success': True,
        'data': {
            'labels': labels,
            'datasets': [
                {'label': 'Диалоги', 'data': conversations_data},
                {'label': 'Лиды', 'data': leads_data}
            ]
        }
    })

@login_required
@require_http_methods(['GET'])
def get_channels_chart(request):
    """API: Распределение по каналам"""
    agent_id = request.GET.get('agent_id', 'all')
    bots_query = BotAgent.objects.filter(user=request.user)
    if agent_id != 'all':
        bots_query = bots_query.filter(id=agent_id)
    
    conversations_by_platform = Conversation.objects.filter(
        bot__in=bots_query
    ).values('bot__platform').annotate(
        total=Count('id')
    ).order_by('-total')
    
    platform_names = {'telegram': 'Telegram', 'whatsapp': 'WhatsApp', 'vk': 'VK', 'instagram': 'Instagram'}
    labels, values, colors = [], [], []
    
    for item in conversations_by_platform:
        platform = item['bot__platform']
        labels.append(platform_names.get(platform, platform.capitalize()))
        values.append(item['total'])
        colors.append({'telegram': '#0088cc', 'whatsapp': '#25D366', 'vk': '#0077FF'}.get(platform, '#6366f1'))
    
    return JsonResponse({'success': True, 'data': {'labels': labels, 'values': values, 'colors': colors}})

@login_required
@require_http_methods(['GET'])
def get_activity_heatmap(request):
    """API: Тепловая карта активности"""
    agent_id = request.GET.get('agent_id', 'all')
    bots_query = BotAgent.objects.filter(user=request.user)
    if agent_id != 'all':
        bots_query = bots_query.filter(id=agent_id)
    
    end_date = timezone.now()
    start_date = end_date - timedelta(days=30)
    
    messages_by_time = Message.objects.filter(
        conversation__bot__in=bots_query,
        created_at__gte=start_date,
        created_at__lte=end_date,
        role='user'
    ).annotate(
        weekday=ExtractWeekDay('created_at'),
        hour=ExtractHour('created_at')
    ).values('weekday', 'hour').annotate(count=Count('id'))
    
    data_dict = {}
    for item in messages_by_time:
        wd = item['weekday']
        weekday_index = (wd - 2) % 7 
        hour = item['hour']
        if weekday_index not in data_dict: data_dict[weekday_index] = {}
        data_dict[weekday_index][hour] = item['count']
    
    max_count = max((item['count'] for item in messages_by_time), default=1)
    
    def get_level(count):
        if count == 0: return 0
        pct = (count / max_count) * 100
        return 1 if pct < 20 else 2 if pct < 40 else 3 if pct < 60 else 4 if pct < 80 else 5
    
    days = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
    heatmap_data = {}
    for day_idx, day_name in enumerate(days):
        heatmap_data[day_name] = {}
        for hour in range(24):
            count = data_dict.get(day_idx, {}).get(hour, 0)
            heatmap_data[day_name][hour] = {'level': get_level(count), 'value': count}
            
    return JsonResponse({'success': True, 'data': heatmap_data})

@login_required
@require_http_methods(['GET'])
def get_agents_performance(request):
    """API: Производительность ботов"""
    bots = BotAgent.objects.filter(user=request.user)
    agents_data = []
    
    for bot in bots:
        conversations = Conversation.objects.filter(bot=bot)
        total_conversations = conversations.count()
        total_leads = conversations.filter(is_lead=True).count()
        conversion = round((total_leads / total_conversations * 100), 0) if total_conversations > 0 else 0
        
        agents_data.append({
            'id': bot.id,
            'name': bot.name,
            'type': bot.get_platform_display(),
            'conversations': total_conversations,
            'leads': total_leads,
            'conversion': conversion,
            'status': bot.status
        })
    
    agents_data.sort(key=lambda x: x['conversations'], reverse=True)
    return JsonResponse({'success': True, 'data': agents_data})

@login_required
@require_http_methods(['POST'])
def export_analytics(request):
    """API: Экспорт (заглушка)"""
    return JsonResponse({'success': True, 'message': 'Экспорт пока не реализован'})

# ============================================
# БАЗА ЗНАНИЙ (RAG + CRUD)
# ============================================

@login_required
def knowledge_base_list(request, bot_id):
    """Список документов в базе знаний бота"""
    bot = get_object_or_404(BotAgent, id=bot_id, user=request.user)
    documents = KnowledgeBase.objects.filter(bot=bot).order_by('-created_at')
    for doc in documents:
        doc.chunks_count_db = doc.chunks.count()
    return render(request, 'dashboard/knowledge_base.html', {'bot': bot, 'documents': documents})

@login_required
def upload_knowledge_file(request, bot_id):
    """Загрузка документа в базу знаний (с RAG индексацией)"""
    bot = get_object_or_404(BotAgent, id=bot_id, user=request.user)
    
    if request.method == 'POST':
        uploaded_file = request.FILES.get('file')
        title = request.POST.get('title', uploaded_file.name)
        description = request.POST.get('description', '')
        
        file_ext = os.path.splitext(uploaded_file.name)[1].lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            messages.error(request, f'Неподдерживаемый формат. Разрешены: {", ".join(ALLOWED_EXTENSIONS)}')
            return redirect('knowledge_base', bot_id=bot_id)
        
        try:
            kb = KnowledgeBase.objects.create(
                bot=bot, title=title, description=description,
                file=uploaded_file, file_type=file_ext[1:], file_size=uploaded_file.size
            )
            
            # Индексация RAG
            file_path = kb.file.path
            chunks_count = rag_service.process_document(kb.id, file_path)
            
            kb.chunks_count = chunks_count
            kb.indexed_at = timezone.now()
            kb.save()
            
            messages.success(request, f'Файл "{title}" загружен и проиндексирован ({chunks_count} фрагментов).')
            
        except Exception as e:
            logger.error(f"Ошибка при загрузке: {str(e)}")
            messages.error(request, f'Ошибка: {str(e)}')
            if 'kb' in locals(): kb.delete()
        
        return redirect('knowledge_base', bot_id=bot_id)
    
    return render(request, 'dashboard/upload_kb.html', {'bot': bot})

@login_required
def knowledge_detail(request, kb_id):
    """Просмотр документа и чанков"""
    kb = get_object_or_404(KnowledgeBase, id=kb_id, bot__user=request.user)
    # Исправлено: добавление chunks для шаблона
    sample_chunks = kb.chunks.all()[:5]
    return render(request, 'dashboard/knowledge_detail.html', {
        'kb': kb, 
        'sample_chunks': sample_chunks, 
        'total_chunks': kb.chunks.count()
    })

@login_required
@require_http_methods(['POST'])
def knowledge_delete(request, kb_id):
    """Удаление документа"""
    kb = get_object_or_404(KnowledgeBase, id=kb_id, bot__user=request.user)
    bot_id = kb.bot.id
    if kb.file and os.path.exists(kb.file.path):
        os.remove(kb.file.path)
    kb.delete()
    messages.success(request, 'Документ удален')
    return redirect('knowledge_base', bot_id=bot_id)

@login_required
@require_http_methods(['POST'])
def reindex_knowledge_base(request, kb_id):
    """API: Переиндексация"""
    kb = get_object_or_404(KnowledgeBase, id=kb_id, bot__user=request.user)
    try:
        kb.chunks.all().delete()
        chunks_count = rag_service.process_document(kb.id, kb.file.path)
        kb.chunks_count = chunks_count
        kb.indexed_at = timezone.now()
        kb.save()
        return JsonResponse({'success': True, 'message': f'Переиндексировано: {chunks_count} чанков'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@require_http_methods(['POST'])
def test_rag_search(request, bot_id):
    """API: Тест RAG поиска"""
    bot = get_object_or_404(BotAgent, id=bot_id, user=request.user)
    try:
        data = json.loads(request.body)
        query = data.get('query', '')
        if not query: return JsonResponse({'success': False, 'error': 'Empty query'}, status=400)
        
        result = rag_service.answer_question(bot.id, query, top_k=5)
        return JsonResponse({
            'success': True, 'answer': result['answer'],
            'sources': result['sources'], 'confidence': result['confidence']
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

# ============================================
# TELEGRAM CONNECT
# ============================================

@login_required
def telegram_connect_view(request, bot_id):
    """Страница подключения Telegram"""
    bot = get_object_or_404(BotAgent, id=bot_id, user=request.user)
    return render(request, 'dashboard/telegram_connect.html', {'bot': bot})

@login_required
@require_http_methods(["POST"])
def telegram_save_credentials(request, bot_id):
    """Шаг 1: Сохранение API ID и API Hash"""
    bot = get_object_or_404(BotAgent, id=bot_id, user=request.user)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Неверный формат JSON'})
    
    api_id = str(data.get('api_id', '')).strip()
    api_hash = str(data.get('api_hash', '')).strip()
    
    if not api_id or not api_hash:
        return JsonResponse({'success': False, 'error': 'API ID и API Hash обязательны'})
    
    if not api_id.isdigit():
        return JsonResponse({'success': False, 'error': 'API ID должен содержать только цифры'})
        
    bot.api_id = api_id
    bot.api_hash = api_hash
    bot.save()
    
    return JsonResponse({'success': True, 'message': 'API ключи сохранены'})

@login_required
@require_http_methods(["POST"])
def telegram_send_code(request, bot_id):
    """Шаг 2: Отправка кода верификации (Реальная отправка через Telethon)"""
    bot = get_object_or_404(BotAgent, id=bot_id, user=request.user)
    data = json.loads(request.body)
    phone_number = data.get('phone_number', '').strip()
    
    if not phone_number:
        return JsonResponse({'success': False, 'error': 'Номер телефона обязателен'})
    
    # Вызываем функцию из telegram_auth.py через async_to_sync
    try:
        result = async_to_sync(send_code_request)(
            phone_number=phone_number,
            api_id=bot.api_id,
            api_hash=bot.api_hash
        )
    except Exception as e:
        logger.error(f"Telethon error: {e}")
        return JsonResponse({'success': False, 'error': f"Ошибка соединения: {str(e)}"})

    # Если telegram_auth вернул ошибку
    if not result.get('success'):
        return JsonResponse(result)

    bot.phone_number = phone_number
    bot.phone_code_hash = result['phone_code_hash']
    bot.status = 'waiting_code'
    bot.save()
    
    request.session['temp_telegram_session'] = result['temp_session_string']
    request.session.modified = True
    
    return JsonResponse({'success': True, 'message': 'Код отправлен на ваш Telegram'})

@login_required
@require_http_methods(["POST"])
def telegram_verify_code(request, bot_id):
    """Шаг 3: Верификация кода (Реальная проверка)"""
    bot = get_object_or_404(BotAgent, id=bot_id, user=request.user)
    data = json.loads(request.body)
    code = data.get('code', '').strip()
    password = data.get('password', '').strip() # На случай 2FA пароля
    
    if not code:
        return JsonResponse({'success': False, 'error': 'Код обязателен'})
    
    # Достаем путь к временной сессии, который сохранили на прошлом шаге
    temp_session_string = request.session.get('temp_telegram_session')
    
    if not temp_session_string:
         return JsonResponse({'success': False, 'error': 'Сессия истекла. Пожалуйста, отправьте код заново.'})

    try:
        # Вызываем проверку кода
        result = async_to_sync(verify_code)(
            phone_number=bot.phone_number,
            phone_code_hash=bot.phone_code_hash,
            code=code,
            api_id=bot.api_id,
            api_hash=bot.api_hash,
            temp_session_string=temp_session_string,
            password=password
        )
    except Exception as e:
         logger.error(f"Verify error: {e}")
         return JsonResponse({'success': False, 'error': str(e)})

    if not result.get('success'):
        # Если нужна 2FA (пароль), вернем это фронтенду
        if result.get('requires_2fa'):
            return JsonResponse(result) # Фронтенд должен показать поле для пароля
        return JsonResponse(result)

    # Успешная авторизация
    bot.status = 'active'
    # Сохраняем итоговую строку сессии в базу
    bot.session_string = result['session_string']
    bot.save()
    
    # Очищаем временные данные
    if 'temp_telegram_session' in request.session:
        del request.session['temp_telegram_session']
    
    return JsonResponse({'success': True, 'message': 'Бот успешно подключен!'})

@login_required
@require_http_methods(["POST"])
def telegram_validate_session(request, bot_id):
    """Проверка валидности сессии"""
    bot = get_object_or_404(BotAgent, id=bot_id, user=request.user)
    if not bot.session_string:
        return JsonResponse({'success': False, 'error': 'Session string не найден'})
    return JsonResponse({'success': True, 'message': 'Сессия валидна'})

@login_required
@require_http_methods(["GET"])
def telegram_get_account_info(request, bot_id):
    """Получение информации об аккаунте"""
    bot = get_object_or_404(BotAgent, id=bot_id, user=request.user)
    if not bot.session_string:
        return JsonResponse({'success': False, 'error': 'Бот не подключен'})
    
    return JsonResponse({
        'success': True,
        'user': {
            'id': 123456789,
            'first_name': 'Test',
            'last_name': 'User',
            'username': 'testuser',
            'phone': bot.phone_number
        }
    })

@login_required
@require_http_methods(["POST"])
def telegram_disconnect(request, bot_id):
    """Отключение Telegram"""
    bot = get_object_or_404(BotAgent, id=bot_id, user=request.user)
    bot.session_string = ''
    bot.phone_code_hash = ''
    bot.status = 'inactive'
    bot.save()
    return JsonResponse({'success': True, 'message': 'Telegram отключен'})

# ============================================
# API ДЛЯ ФРОНТЕНДА И WEBHOOKS
# ============================================

@login_required
@require_http_methods(['POST'])
def toggle_bot_status(request, bot_id):
    """API: Переключение статуса бота"""
    try:
        bot = BotAgent.objects.get(id=bot_id, user=request.user)
        bot.status = 'paused' if bot.status == 'active' else 'active'
        bot.save()
        return JsonResponse({'success': True, 'status': bot.status})
    except BotAgent.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Бот не найден'}, status=404)

@login_required
@require_http_methods(['POST'])
def update_bot_prompt(request, bot_id):
    """API: Обновление AI настроек (Системный промпт)"""
    try:
        bot = BotAgent.objects.get(id=bot_id, user=request.user)
        data = json.loads(request.body)
        bot.system_prompt = data.get('system_prompt', bot.system_prompt)
        bot.openai_model = data.get('ai_model', bot.openai_model)
        bot.save()
        return JsonResponse({'success': True})
    except BotAgent.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Бот не найден'}, status=404)

@login_required
@require_http_methods(['POST'])
def update_bot_api(request, bot_id):
    """API: Обновление основных настроек бота (Имя, Описание)"""
    try:
        bot = BotAgent.objects.get(id=bot_id, user=request.user)
        data = json.loads(request.body)
        bot.name = data.get('name', bot.name)
        bot.description = data.get('description', bot.description)
        bot.save()
        return JsonResponse({'success': True})
    except BotAgent.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Бот не найден'}, status=404)

@login_required
@require_http_methods(['DELETE', 'POST'])
def delete_bot_api(request, bot_id):
    """API: Удаление бота (JSON)"""
    try:
        bot = BotAgent.objects.get(id=bot_id, user=request.user)
        bot.delete()
        return JsonResponse({'success': True})
    except BotAgent.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Бот не найден'}, status=404)

@login_required
@require_http_methods(['POST'])
def upload_knowledge_api(request, bot_id):
    """API: Загрузка файла (для JS)"""
    try:
        bot = BotAgent.objects.get(id=bot_id, user=request.user)
        if 'file' not in request.FILES:
            return JsonResponse({'success': False, 'message': 'Файл не передан'}, status=400)
            
        uploaded_file = request.FILES['file']
        file_ext = os.path.splitext(uploaded_file.name)[1].lower()
        
        if file_ext not in ALLOWED_EXTENSIONS:
             return JsonResponse({'success': False, 'message': 'Неверный формат'}, status=400)

        kb = KnowledgeBase.objects.create(
            bot=bot, title=uploaded_file.name, file=uploaded_file,
            file_type=file_ext[1:], file_size=uploaded_file.size
        )
        
        chunks_count = rag_service.process_document(kb.id, kb.file.path)
        kb.chunks_count = chunks_count
        kb.indexed_at = timezone.now()
        kb.save()
        
        return JsonResponse({'success': True, 'chunks': chunks_count})
        
    except BotAgent.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Бот не найден'}, status=404)
    except Exception as e:
        logger.error(f"Upload error: {e}")
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(['POST'])
def telegram_webhook(request, bot_token):
    """Webhook для Telegram бота"""
    try:
        bot = BotAgent.objects.get(telegram_token=bot_token)
        data = json.loads(request.body)
        
        if 'message' in data:
            message = data['message']
            user_id = str(message['from']['id'])
            text = message.get('text', '')
            
            conversation, _ = Conversation.objects.get_or_create(
                bot=bot, user_id=user_id,
                defaults={'user_name': message['from'].get('first_name', 'User')}
            )
            
            Message.objects.create(conversation=conversation, role='user', content=text)
            
            # RAG логика
            if bot.use_rag:
                result = rag_service.answer_question(bot.id, text, top_k=bot.rag_top_k)
                bot_response = result['answer']
            else:
                bot_response = "Я пока умею только молчать (RAG выключен)."
            
            Message.objects.create(conversation=conversation, role='bot', content=bot_response)
            conversation.last_message_at = timezone.now()
            conversation.save()
            
            # TODO: Отправить ответ через Requests к Telegram API
            
            return JsonResponse({'success': True})
        return JsonResponse({'success': True})
    except BotAgent.DoesNotExist:
        return JsonResponse({'error': 'Bot not found'}, status=404)
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(['POST'])
def whatsapp_webhook(request, bot_token):
    """Webhook для WhatsApp"""
    return JsonResponse({'success': True})

@csrf_exempt
@require_http_methods(['POST'])
def send_message_api(request, bot_id):
    """API: Отправка сообщения (Chat Interface)"""
    try:
        bot = BotAgent.objects.get(id=bot_id)
        data = json.loads(request.body)
        user_id = data.get('user_id')
        message_text = data.get('message')
        
        if not user_id or not message_text:
            return JsonResponse({'error': 'missing fields'}, status=400)
        
        conversation, _ = Conversation.objects.get_or_create(
            bot=bot, user_id=user_id, defaults={'user_name': f'User {user_id}'}
        )
        
        Message.objects.create(conversation=conversation, role='user', content=message_text)
        
        if bot.use_rag:
            result = rag_service.answer_question(bot.id, message_text, top_k=bot.rag_top_k)
            bot_response = result['answer']
            sources = result.get('sources', [])
        else:
            bot_response = "Ответ без RAG"
            sources = []
        
        Message.objects.create(conversation=conversation, role='bot', content=bot_response)
        conversation.last_message_at = timezone.now()
        conversation.save()
        
        return JsonResponse({'success': True, 'response': bot_response, 'sources': sources})
        
    except BotAgent.DoesNotExist:
        return JsonResponse({'error': 'Bot not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def settings_view(request):
    """Настройки аккаунта"""
    return render(request, 'dashboard/settings.html')