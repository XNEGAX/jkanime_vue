#!/bin/sh
set -e

# Use mounted volume for persistent data
export DATABASE_DIR="/data"
export DOWNLOAD_DIR="/data/descargas"
export MEDIA_DIR="/data/media"

cd /app/jkanime_vue

# Ensure directories exist on volume
mkdir -p "$DATABASE_DIR" "$DOWNLOAD_DIR" "$MEDIA_DIR"

# Symlink database to volume if not already there
if [ ! -f "$DATABASE_DIR/db.sqlite3" ] && [ -f "/app/jkanime_vue/db.sqlite3" ]; then
    cp /app/jkanime_vue/db.sqlite3 "$DATABASE_DIR/db.sqlite3"
fi
ln -sf "$DATABASE_DIR/db.sqlite3" /app/jkanime_vue/db.sqlite3

# Symlink media to volume
rm -rf /app/jkanime_vue/media
ln -sf "$MEDIA_DIR" /app/jkanime_vue/media

# Symlink descargas to volume
rm -rf /app/jkanime_vue/descargas
ln -sf "$DOWNLOAD_DIR" /app/jkanime_vue/descargas

echo "Running migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Creating superuser if needed..."
python manage.py shell -c "
from django.contrib.auth.models import User
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print('Superuser created')
else:
    print('Superuser already exists')
"

echo "Starting Django server..."
cd /app/jkanime_vue
gunicorn jkanime_vue.wsgi:application --bind 0.0.0.0:8000 --workers 2 --timeout 120 &
DJANGO_PID=$!

echo "Starting Celery worker (descargas)..."
celery -A jkanime_vue worker -l info -Q descargas --concurrency=2 -P prefork &
CELERY_DESCARGAS_PID=$!

echo "Starting Celery worker (actualizaciones)..."
celery -A jkanime_vue worker -l info -Q actualizaciones --concurrency=1 -P prefork &
CELERY_ACTUALIZACIONES_PID=$!

echo "All services started."
wait $DJANGO_PID $CELERY_DESCARGAS_PID $CELERY_ACTUALIZACIONES_PID
