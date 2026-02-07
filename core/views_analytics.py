# core/views_analytics.py
import json
import csv
from datetime import timedelta
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.db.models import Count, Q
from django.db.models.functions import TruncDate, ExtractWeekDay, ExtractHour
from django.utils import timezone
from .models import BotAgent, Conversation, Message, Analytics

@login_required
def get_analytics_summary(request):
    """API: Сводная статистика (Карточки сверху)"""
    agent_id = request.GET.get('agent_id', 'all')
    period = request.GET.get('period', '7days')
    
    # 1. Определяем диапазон дат
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
    
    # 2. Фильтруем ботов пользователя
    bots = BotAgent.objects.filter(user=request.user)
    if agent_id != 'all':
        bots = bots.filter(id=agent_id)
    
    # 3. Получаем диалоги за период
    conversations = Conversation.objects.filter(
        bot__in=bots,
        started_at__date__gte=start_date,
        started_at__date__lte=end_date
    )
    
    # 4. Считаем метрики
    total_conversations = conversations.count()
    total_leads = conversations.filter(is_lead=True).count()
    
    # Считаем сообщения через связь с отфильтрованными диалогами
    total_messages = Message.objects.filter(
        conversation__in=conversations
    ).count()
    
    conversion_rate = (total_leads / total_conversations * 100) if total_conversations > 0 else 0
    
    # 5. Считаем изменения (сравнение с прошлым периодом)
    period_days = (end_date - start_date).days + 1
    prev_start = start_date - timedelta(days=period_days)
    prev_end = start_date - timedelta(days=1)
    
    prev_conversations = Conversation.objects.filter(
        bot__in=bots,
        started_at__date__gte=prev_start,
        started_at__date__lte=prev_end
    ).count()
    
    prev_leads = Conversation.objects.filter(
        bot__in=bots,
        started_at__date__gte=prev_start,
        started_at__date__lte=prev_end,
        is_lead=True
    ).count()

    def calc_change(curr, prev):
        if prev == 0:
            return 100 if curr > 0 else 0
        return round(((curr - prev) / prev) * 100, 1)

    return JsonResponse({
        'success': True,
        'data': {
            'total_conversations': total_conversations,
            'total_leads': total_leads,
            'total_messages': total_messages,
            'conversion_rate': round(conversion_rate, 1),
            'changes': {
                'conversations': calc_change(total_conversations, prev_conversations),
                'leads': calc_change(total_leads, prev_leads),
                'messages': 0, # Можно дореализовать
                'conversion': 0 
            }
        }
    })

@login_required
def get_conversations_chart(request):
    """API: График диалогов и лидов по дням"""
    agent_id = request.GET.get('agent_id', 'all')
    period = request.GET.get('period', '7days')
    
    now = timezone.now()
    end_date = now.date()
    
    if period == 'today':
        start_date = end_date
    elif period == '30days':
        start_date = end_date - timedelta(days=30)
    else:
        start_date = end_date - timedelta(days=7)
        
    bots = BotAgent.objects.filter(user=request.user)
    if agent_id != 'all':
        bots = bots.filter(id=agent_id)
        
    # Группировка по дате
    data = Conversation.objects.filter(
        bot__in=bots,
        started_at__date__gte=start_date,
        started_at__date__lte=end_date
    ).annotate(
        date=TruncDate('started_at')
    ).values('date').annotate(
        total=Count('id'),
        leads=Count('id', filter=Q(is_lead=True))
    ).order_by('date')
    
    # Заполнение пропусков дат
    date_map = {item['date']: item for item in data}
    labels = []
    dataset_total = []
    dataset_leads = []
    
    curr = start_date
    while curr <= end_date:
        labels.append(curr.strftime('%d.%m'))
        if curr in date_map:
            dataset_total.append(date_map[curr]['total'])
            dataset_leads.append(date_map[curr]['leads'])
        else:
            dataset_total.append(0)
            dataset_leads.append(0)
        curr += timedelta(days=1)
        
    return JsonResponse({
        'success': True,
        'data': {
            'labels': labels,
            'datasets': [
                {'label': 'Диалоги', 'data': dataset_total},
                {'label': 'Лиды', 'data': dataset_leads}
            ]
        }
    })

@login_required
def get_channels_chart(request):
    """API: Круговая диаграмма по каналам"""
    agent_id = request.GET.get('agent_id', 'all')
    bots = BotAgent.objects.filter(user=request.user)
    
    if agent_id != 'all':
        bots = bots.filter(id=agent_id)
        
    stats = Conversation.objects.filter(bot__in=bots).values('bot__platform').annotate(count=Count('id'))
    
    labels = []
    values = []
    colors = []
    
    platform_map = {
        'telegram': ('Telegram', '#0088cc'),
        'whatsapp': ('WhatsApp', '#25D366'),
        'instagram': ('Instagram', '#E1306C'),
        'vk': ('VK', '#0077FF'),
    }
    
    for item in stats:
        code = item['bot__platform']
        name, color = platform_map.get(code, (code, '#999'))
        labels.append(name)
        values.append(item['count'])
        colors.append(color)
        
    return JsonResponse({
        'success': True,
        'data': {
            'labels': labels,
            'values': values,
            'colors': colors
        }
    })

@login_required
def get_activity_heatmap(request):
    """API: Тепловая карта активности"""
    agent_id = request.GET.get('agent_id', 'all')
    bots = BotAgent.objects.filter(user=request.user)
    if agent_id != 'all':
        bots = bots.filter(id=agent_id)
        
    # Анализируем сообщения пользователей за последние 30 дней
    start_date = timezone.now() - timedelta(days=30)
    
    stats = Message.objects.filter(
        conversation__bot__in=bots,
        created_at__gte=start_date,
        role='user'
    ).annotate(
        weekday=ExtractWeekDay('created_at'), # 1=Воскресенье, 2=Понедельник... (Зависит от БД, обычно так)
        hour=ExtractHour('created_at')
    ).values('weekday', 'hour').annotate(count=Count('id'))
    
    # Формируем матрицу
    # Django ExtractWeekDay: 1=Sun, 2=Mon, ..., 7=Sat
    # Нам нужно: 0=Mon, ..., 6=Sun
    
    matrix = {} # {day_index: {hour: count}}
    max_val = 0
    
    for item in stats:
        # Конвертация дня недели (Django 1=Sun -> Python 6=Sun)
        wd_django = item['weekday']
        wd_python = (wd_django - 2) % 7
        
        hour = item['hour']
        count = item['count']
        if count > max_val: max_val = count
        
        if wd_python not in matrix: matrix[wd_python] = {}
        matrix[wd_python][hour] = count
        
    # Формируем ответ для фронта
    days = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
    result = {}
    
    for d_idx, d_name in enumerate(days):
        result[d_name] = {}
        for h in range(24):
            val = matrix.get(d_idx, {}).get(h, 0)
            # Уровень интенсивности 0-5
            level = 0
            if val > 0:
                level = int((val / max_val) * 5) if max_val > 0 else 1
                if level == 0: level = 1
                
            result[d_name][h] = {'value': val, 'level': level}
            
    return JsonResponse({'success': True, 'data': result})

@login_required
def get_agents_performance(request):
    """API: Таблица эффективности ботов"""
    bots = BotAgent.objects.filter(user=request.user)
    data = []
    
    for bot in bots:
        convs = Conversation.objects.filter(bot=bot).count()
        leads = Conversation.objects.filter(bot=bot, is_lead=True).count()
        conv_rate = round((leads / convs * 100), 1) if convs > 0 else 0
        
        data.append({
            'id': bot.id,
            'name': bot.name,
            'type': bot.get_platform_display(),
            'conversations': convs,
            'leads': leads,
            'conversion': conv_rate,
            'status': bot.status
        })
        
    # Сортировка по кол-ву диалогов
    data.sort(key=lambda x: x['conversations'], reverse=True)
    
    return JsonResponse({'success': True, 'data': data})

@login_required
def export_analytics(request):
    """API: Экспорт в CSV (простая реализация)"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="analytics.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Bot', 'Date', 'Conversations', 'Leads'])
    
    analytics = Analytics.objects.filter(bot__user=request.user).order_by('-date')
    
    for row in analytics:
        writer.writerow([
            row.bot.name,
            row.date,
            row.conversations_count,
            row.leads_count
        ])
        
    return response