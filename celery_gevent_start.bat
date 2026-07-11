@echo off
cd /d C:\Users\xnega\Documents\Proyectos\jkanime_vue\jkanime_vue
set DJANGO_SETTINGS_MODULE=jkanime_vue.settings
"C:\Users\xnega\AppData\Local\Python\pythoncore-3.14-64\python.exe" -m celery -A jkanime_vue worker --loglevel=info --pool=gevent --concurrency=3
