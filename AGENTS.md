<!-- jkanime_vue — Vue 3 + Django 6 DRF + Celery anime series manager (XNEGAX/jkanime_vue) -->

## Stack
- **Frontend**: Vue 3 + Vite 6 + Pinia + Vue Router 4 (`frontend/src/`)
- **Backend**: Django 6+ / DRF (`backend/config/`), app `series/`
- **Queue**: threading + queue.Queue — 10 workers, estado en memoria

## Quick start
```
run.bat
```
Handles everything: venv creation, pip install, npm install+build, Redis, Celery, Django.

Manual: `python run.py` (requires existing venv + built frontend).

**No lint/typecheck/test commands available** — the repo has none configured.

## Start order (from run.py)
1. Kills previous process on port 8000
2. Starts 10 background threading workers (descargas + verificacion)
3. Django `manage.py runserver 0.0.0.0:8000`
4. Opens `http://127.0.0.1:8000`

## Architecture
- SPA: Django serves `frontend/dist/index.html` for all non-API/non-asset routes
- API: `/api/` → DRF (`series.urls`)
- Admin: `/admin/`
- Static assets: `/assets/` from `frontend/dist/assets/`
- Media: `/media/` in dev mode
- CORS wide open, DRF `AllowAny`

## Tareas en background (threading)
- `task_runner.py` — cola FIFO con 10 workers daemon, estado en memoria (dict thread-safe)
- `tasks.py` — core de descarga/verificacion, sin Celery
- Progreso via `task_runner.update_task(task_id, ...)` → polling desde el frontend

## Frontend dev server (separate from Django)
```
cd frontend
npm run dev    # Vite on port 5173, proxies /api and /media to :8000
```
Vite proxy is configured in `vite.config.js`. Vue Router routes: `/` (series), `/serie/:id` (chapters), `/reproducir/:id` (player), `/favoritos`.

## DB & storage
- SQLite at `backend/db.sqlite3`
- `backend/manage.py` runs from the `backend/` subdirectory, settings module `config.settings`
- Settings locale: `es`, timezone `America/Santiago`
- Downloads stored at `backend/descargas/<slug>/`
- Cover art: `backend/media/portadas/`
- Both `db.sqlite3` and `descargas/` are gitignored

## Environment quirks
- **Windows-only**: uses `taskkill`, `netstat`, `winget`, `CREATE_NO_WINDOW` flags
- **Redis dump.rdb**: Redis produces `dump.rdb` in its cwd (root and `frontend/` are gitignored)
- Scraper targets `jkanime.net` with `cloudscraper` + `beautifulsoup4`
- Utility: `check_sao.py` — standalone test for cloudatacdn video downloads
