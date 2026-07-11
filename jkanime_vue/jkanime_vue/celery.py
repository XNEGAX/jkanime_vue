import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'jkanime_vue.settings')

app = Celery('jkanime_vue')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
