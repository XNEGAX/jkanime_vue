<!-- jkanime_vue — Vue 3 + Django 6 DRF + Celery anime series manager (XNEGAX/jkanime_vue) -->

## Stack
- **Frontend**: Vue 3 + Vite 6 + Pinia + Vue Router 4 (`frontend/src/`)
- **Backend**: Django 6+ / DRF (`jkanime_vue/jkanime_vue/`), app `series/`
- **Queue**: Celery + Redis (broker) — two workers, SQLite DB
- **Android TV**: Kotlin/Gradle subproject at `android_tv/` (app name `jkanime_tv`)
- **Android Phone**: Kotlin/Gradle subproject at `android_phone/` (app name `jkanime_phone`, package `com.jkanime.phone`)

## Quick start
```
run.bat
```
Handles everything: venv creation, pip install, npm install+build, Redis, Celery, Django.

Manual: `python run.py` (requires existing venv + built frontend).

**No lint/typecheck/test commands available** — the repo has none configured.

## Start order (from run.py)
1. Redis (port 6379) — auto-starts `redis-server` if not running. Install: `winget install taizod1024.redis-windows-fork`
2. Kills previous processes on port 8000 + Celery windows
3. Celery worker `descargas` (gevent, concurrency=10, queue=descargas)
4. Celery worker `actualizaciones` (solo, concurrency=1, queue=actualizaciones)
5. Django `manage.py runserver 0.0.0.0:8000`
6. Opens `http://127.0.0.1:8000`

## Architecture
- SPA: Django serves `frontend/dist/index.html` for all non-API/non-asset routes
- API: `/api/` → DRF (`series.urls`)
- Admin: `/admin/`
- Static assets: `/assets/` from `frontend/dist/assets/`
- Media: `/media/` in dev mode
- CORS wide open, DRF `AllowAny`

## Celery task routes
- `series.tasks.verificar_series_task` → queue `actualizaciones`
- `series.tasks.descargar_capitulo` / `descargar_todos` → queue `descargas`
- Broker/backend: `redis://127.0.0.1:6379/0`
- Debug: `celery_debug.bat` runs with `--pool=prefork --concurrency=1 --loglevel=debug`

## Frontend dev server (separate from Django)
```
cd frontend
npm run dev    # Vite on port 5173, proxies /api and /media to :8000
```
Vite proxy is configured in `vite.config.js`. Vue Router routes: `/` (series), `/serie/:id` (chapters), `/reproducir/:id` (player), `/favoritos`.

## DB & storage
- SQLite at `jkanime_vue/db.sqlite3`
- `jkanime_vue/manage.py` runs from the `jkanime_vue/` subdirectory, settings module `jkanime_vue.settings`
- Settings locale: `es`, timezone `America/Santiago`
- Downloads stored at `jkanime_vue/descargas/<slug>/`
- Cover art: `jkanime_vue/media/portadas/`
- Both `db.sqlite3` and `descargas/` are gitignored

## Environment quirks
- **Windows-only**: uses `taskkill`, `netstat`, `winget`, `CREATE_NO_WINDOW` flags
- **Redis dump.rdb**: Redis produces `dump.rdb` in its cwd (root and `frontend/` are gitignored)
- Scraper targets `jkanime.net` with `cloudscraper` + `beautifulsoup4`
- Utility: `check_sao.py` — standalone test for cloudatacdn video downloads
