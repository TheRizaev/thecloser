# config/celery.py
"""
Конфигурация Celery для асинхронных задач
"""

import os
from celery import Celery

# Устанавливаем настройки Django для Celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Создаем экземпляр Celery
app = Celery('salesai')

# Загружаем конфигурацию из Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Автоматически находим задачи в файлах tasks.py всех приложений
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Тестовая задача для отладки"""
    print(f'Request: {self.request!r}')