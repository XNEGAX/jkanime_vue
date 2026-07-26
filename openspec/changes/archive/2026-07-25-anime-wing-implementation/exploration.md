# Exploration: anime-wing-implementation

Comprehensive codebase analysis of the jkanime_vue project (to be rebranded as **AnimeWing**).

---

## 1. Backend Architecture

### Project Structure

```
backend/
├── config/
│   ├── __init__.py
│   ├── settings.py          # Django settings (DEBUG=True, SQLite, es locale)
│   ├── urls.py              # Root URLs: /admin/, /api/, SPA fallback, /assets/
│   ├── asgi.py
│   └── wsgi.py
├── series/                  # Single Django app
│   ├── models.py            # Serie, Capitulo
│   ├── serializers.py       # 4 serializers
│   ├── views.py             # 20+ DRF function-based views
│   ├── urls.py              # 25 URL patterns
│   ├── admin.py             # Basic admin registration
│   ├── apps.py              # SeriesConfig — starts 50 workers on ready()
│   ├── scraper.py           # Backward-compat shim → scrapers/
│   ├── tasks.py             # Download/verify core logic (threading)
│   ├── task_runner.py       # Queue + worker pool + in-memory state
│   ├── management/commands/
│   │   └── rename_descargas.py  # Utility: rename downloaded files
│   └── scrapers/
│       ├── __init__.py      # Registry pattern + get_scraper() factory
│       ├── base.py          # BaseScraper ABC
│       ├── jkanime.py       # JKanimeScraper (jkanime.net)
│       ├── latanime.py      # LatanimeScraper (latanime.org)
│       └── resolvers.py     # Video URL resolvers per server type
├── db.sqlite3               # SQLite database
├── descargas/               # Downloaded .mp4 files (gitignored)
├── media/                   # Uploaded cover art
│   ├── portadas/            # Serie cover images
│   ├── logo.png
│   └── PI_Wing_Zero_Mercy.webp  # Official AnimeWing logo
└── manage.py
```

### Models (`backend/series/models.py`)

**Serie**
- `nombre` (CharField 255)
- `anio` (IntegerField, default 2024)
- `portada` (ImageField, upload_to='portadas/')
- `url` (URLField 500) — source URL
- `slug` (SlugField 255, auto-generated from URL)
- `favorito` (BooleanField, default False)
- `estado` (CharField: 'en_emision' | 'concluido' | 'desconocido')
- `dia_emision` (CharField: lunes-domingo or '')
- `fuente` (CharField, default 'jkanime') — supports 'jkanime' and 'latanime'
- `created_at` (DateTimeField, auto_now_add)
- Table: `serie`, ordered by nombre

**Capitulo** (note: NOT "Episodio" — model uses "Capitulo")
- `serie` (FK → Serie, related_name='capitulos')
- `numero` (IntegerField)
- `fecha_publicacion` (DateTimeField, nullable)
- `ruta_archivo` (CharField 500, nullable) — absolute path to downloaded .mp4
- `url_fuente` (URLField 500) — source episode URL
- `ultimo_segundo` (IntegerField, default 0) — resume position
- `archivo_existe` (property) — checks if ruta_archivo file exists on disk
- `nombre_archivo` (property) — returns `Episodio-{numero}.mp4`
- Table: `capitulo`, unique_together: [serie, numero], ordered by numero

### Serializers (`backend/series/serializers.py`)

| Serializer | Purpose | Key Fields |
|---|---|---|
| `CapituloSerializer` | Episode list in series detail | id, numero, nombre_archivo, archivo_existe, url_fuente, fecha_publicacion, ruta_smb, ultimo_segundo |
| `SerieListSerializer` | Series listing | id, nombre, anio, portada_url, slug, favorito, estado, dia_emision, latest_fecha, capitulos_count, descargados_count |
| `SerieDetailSerializer` | Single series with episodes | Same as list + nested capitulos (CapituloSerializer) |
| `CapituloDetailSerializer` | Single episode for player | All fields + serie_nombre, serie_id, anterior_id, siguiente_id |

Note: `ruta_smb` is a computed field returning `{slug}/{nombre_archivo}` for potential SMB/network play.

### API Endpoints (`backend/series/urls.py`)

All under `/api/` prefix:

| Method | Endpoint | View | Purpose |
|---|---|---|---|
| GET | `/series/` | `api_series` | List all series (search param) |
| GET | `/series/favoritos/` | `api_series_favoritos` | List favorites (filter by estado) |
| POST | `/series/{id}/favorito/` | `api_toggle_favorito` | Toggle favorite |
| DELETE | `/series/{id}/eliminar/` | `api_eliminar_serie` | Delete series + files |
| GET | `/series/{id}/` | `api_serie_detail` | Series detail with chapters |
| GET | `/series/{id}/capitulos/` | `api_capitulos` | List chapters (triggers scrape for new) |
| GET/POST | `/series/verificar/` | `api_verificar_series` | Background verification |
| POST | `/series/agregar-url/` | `api_agregar_serie_url` | Add series by URL (jkanime/latanime) |
| POST | `/series/{id}/descargar-todos/` | `api_descargar_todos` | Download all missing episodes |
| POST | `/series/{id}/refrescar-portada/` | `api_refrescar_portada` | Re-download cover art |
| GET | `/capitulos/{id}/` | `api_capitulo_detail` | Episode detail |
| POST | `/capitulos/{id}/descargar/` | `api_descargar_capitulo` | Start single download |
| POST | `/capitulos/{id}/progreso/` | `api_guardar_progreso` | Save resume position |
| GET | `/capitulos/{id}/verificar/` | `api_verificar_archivo` | Check MP4 validity |
| POST | `/capitulos/{id}/reparar/` | `api_reparar_capitulo` | Delete corrupt + re-download |
| GET | `/tareas/activas/` | `api_tareas_activas` | Active background tasks |
| GET | `/tareas/{id}/` | `api_estado_tarea` | Task status/progress |
| POST | `/tareas/{id}/cancelar/` | `api_cancelar_tarea` | Cancel task + clean .part files |
| GET | `/video/{id}/` | `api_servir_video` | Stream MP4 with range support |
| GET | `/ultimos-episodios/` | `api_ultimos_episodios` | Trending episodes from jkanime.net |

### Scraping Logic

**Registry Pattern** (`scrapers/__init__.py`):
- `SCRAPER_REGISTRY` dict maps source names to classes
- `get_scraper(source)` factory returns fresh instance per call
- Falls back to 'jkanime' if unknown source

**BaseScraper ABC** (`scrapers/base.py`):
- `get_all_series()` → [{slug, nombre, url, cover_url}]
- `get_series_info(url)` → {slug, nombre, cover_url, estado, es_pelicula, dia_emision}
- `get_episodes(slug)` → [{numero, url, timestamp}]
- `get_download_urls(episode_url)` → [{server, url, size}]

**JKanimeScraper** (`scrapers/jkanime.py`):
- Uses cloudscraper + BeautifulSoup
- Scrapes homepage tabs (#animes, #donghuas, #ovas)
- Episodes via AJAX pagination (`/ajax/episodes/{anime_id}/{page}`)
- Download URLs from inline JS `var servers = [...]`
- Server priority: Mediafire > Mega > Mp4upload > Streamtape > VOE > ...
- Cover images from CDN: `https://cdn.jkdesa.com/assets/images/animes/image/{slug}.jpg`

**LatanimeScraper** (`scrapers/latanime.py`):
- Same interface, different HTML parsing
- Paginated directory at `/animes?page=N`
- Episodes from `a[href*='/ver/']` links
- Download URLs from direct-links + play-video data-player base64

**Video Resolvers** (`scrapers/resolvers.py`):
- Dedicated resolvers: Mediafire, Mega, Mp4upload, Streamtape, VOE, Doodstream
- Generic MP4 resolver for: Filemoon, Mixdrop, Lulu, Listeamed, Streamwish, Vidhide
- Each returns direct .mp4/.m3u8 URL or None

### Background Tasks

**task_runner.py** — In-memory queue + worker pool:
- `queue.Queue` FIFO with 10 workers (AGENTS.md says 10, AppConfig starts 50)
- Thread-safe `_tasks` dict with Lock
- `_cancel_flags` dict for cancellation
- States: PENDING → PROGRESS → SUCCESS | FAILURE | CANCELLED
- Functions: `enqueue_download()`, `enqueue_descargar_todos()`, `enqueue_verificar()`

**tasks.py** — Core download/verify logic:
- `_descargar_capitulo_core()`: Get download URLs → try each server → stream → validate MP4 → save
- `_run_download()`: Single episode download with progress
- `_run_descargar_todos()`: Batch download with progress
- `_run_verificar()`: Scrape JKanime for new series, update estado/dia_emision
- MP4 validation: ftyp header check + moov/mdat atom presence + minimum 1MB

### Database Configuration
- SQLite at `backend/db.sqlite3`
- Locale: `es`, Timezone: `America/Santiago`
- DOWNLOAD_DIR: `backend/descargas/`
- CORS: AllowAll origins
- DRF: AllowAny permissions, no pagination

---

## 2. Frontend Architecture

### Project Structure

```
frontend/src/
├── main.js              # App bootstrap, Pinia + Router, Capacitor detection
├── App.vue              # Root: ConfigScreen | (Sidebar + Navbar + RouterView + DownloadDrawer)
├── style.css            # Global styles (dark theme: #0f0f0f bg, #e94560 accent)
├── api/
│   └── index.js         # Axios instance + all API functions (25+ exports)
├── router/
│   └── index.js         # 4 routes (see below)
├── stores/
│   ├── config.js        # Server config (host/port) via Capacitor Preferences
│   ├── downloads.js     # Download state management + polling
│   └── favorites.js     # Favorite state (Set-based)
├── views/
│   ├── SeriesView.vue   # Home: day-grouped series table with pagination
│   ├── ChaptersView.vue # Series detail: episode list + download/play buttons
│   ├── PlayerView.vue   # Standalone player (redirected to /, NOT active)
│   └── FavoritesView.vue # 3-tab view: trending + en emisión + concluidos
└── components/
    ├── AppSidebar.vue       # Fixed left sidebar (Home + Favoritos)
    ├── AppNavbar.vue        # Top navbar: brand + search + "Add URL" modal + download badge
    ├── ConfigScreen.vue     # Capacitor initial config (host/port)
    ├── DownloadDrawer.vue   # Right-side sliding drawer for active downloads
    ├── DownloadItem.vue     # Single download item with progress
    └── VideoPlayerModal.vue # Full-screen video player modal (active player)
```

### Vue Router (`frontend/src/router/index.js`)

| Path | Name | Component | Notes |
|---|---|---|---|
| `/` | `series` | SeriesView | Home page, day-grouped series |
| `/serie/:id` | `chapters` | ChaptersView | Series detail + episode list |
| `/reproducir/:id` | — | **redirect → /** | PlayerView is NOT used; redirect to home |
| `/favoritos` | `favorites` | FavoritesView | 3-tab favorites view |

**Key routing observation**: `/reproducir/:id` redirects to `/` — the actual player is `VideoPlayerModal.vue`, a teleported fullscreen overlay triggered by `playerCapituloId` ref in views.

### Pinia Stores

**config.js** — Server configuration:
- Stores `host` + `port` via Capacitor Preferences
- `baseUrl` computed: `http://{host}:{port}`
- `isCapacitor` flag for native detection
- On Capacitor, shows ConfigScreen before app loads
- Web mode: uses Vite proxy (no config needed)

**downloads.js** — Download management:
- `downloads` ref array with taskId, capituloId, state, progress fields
- `addDownload()` adds item + starts 1.5s polling interval
- `restoreFromServer()` recovers active tasks on page load
- `cancelDownload()` calls API + stops polling
- `drawerOpen` toggle for DownloadDrawer
- Callbacks system: `onComplete` callback fires on SUCCESS

**favorites.js** — Favorite state:
- `Set`-based storage (not persisted locally — loaded from API)
- `toggle(id)` calls API and updates local state
- `loadFromSeries(seriesList)` bulk-loads from series data

### API Layer (`frontend/src/api/index.js`)

Axios instance with interceptor that prepends `baseUrl/api` (Capacitor) or `/api` (web proxy).

25+ exported functions covering all endpoints. Key patterns:
- `getVideoUrl(id)` — returns URL string (not Axios call)
- `getGuardarProgresoUrl(id)` — returns URL for sendBeacon
- `guardarProgreso(id, segundo)` — POST with {segundo}
- All other functions return Axios promises

### Views Detail

**SeriesView.vue** — Home page:
- Loads all series via `getSeries()`
- Filters: excludes concluido series, excludes series with latest_fecha > 2 weeks old
- Groups by `dia_emision`, paginated one group per page
- Groups rotated to start from today's day
- Auto-triggers verification on mount (scrapes JKanime for updates)
- Features: search (URL query param), favorite toggle, delete series

**ChaptersView.vue** — Series detail:
- Loads series detail + chapters (triggers scrape for new episodes)
- Episode table with Play/Download/Repair buttons
- Button logic: archivo_existe → verify MP4 → play or repair
- Download: calls API → addDownload → auto-play on complete
- "Download All" for batch operations
- Resume badge showing saved position (m:ss format)

**FavoritesView.vue** — 3-tab interface:

*Tab 1: "Últimos episodios"* (trending):
- Calls `/api/ultimos-episodios/`
- Groups by `tab` field (Animes, Donghuas, Ovas)
- Uses inline `trending-card` + `trending-grid` styles
- Click: verify episode → play or download + play
- Download overlay on card: spinner + progress bar + percentage

*Tab 2: "En emisión"*:
- Calls `/api/series/favoritos/?estado=en_emision`
- Groups by `dia_emision`, rotated from today backwards
- Uses trending-card grid
- Search filtering

*Tab 3: "Concluidos"*:
- Calls `/api/series/favoritos/?estado=concluido`
- Groups alphabetically by first letter
- Uses trending-card grid
- Shows downloaded/total counts

**VideoPlayerModal.vue** — The active player:
- Full-screen Teleport overlay
- Native HTML5 `<video>` element (NOT Plyr — that's in unused PlayerView)
- Features: resume from last position, skip opening (+90s), keyboard shortcuts
- Progress saving: every 10 seconds + on pause + on beforeunload (beacon)
- Error handling: detect corrupt video → offer repair
- Navigation: anterior/siguiente episode buttons
- Keyboard: Space=play/pause, Arrows=seek, F=fullscreen, S=skip OP, Esc=close

**PlayerView.vue** — UNUSED:
- Full Plyr integration (controls, speed settings, keyboard)
- Route `/reproducir/:id` redirects to `/`
- This is dead code — the active player is VideoPlayerModal

### Components Detail

**AppSidebar.vue**: Fixed 60px left sidebar, two links (Home 🏠, Favoritos ♥), active state highlight.

**AppNavbar.vue**: Sticky top navbar with brand "JKanime Gestor", search input (debounced 300ms), "Add URL" modal (Teleported), download badge with active count + pulse animation.

**ConfigScreen.vue**: Shown only on Capacitor when not configured. Host + port inputs, connection test, saves to Preferences.

**DownloadDrawer.vue**: Right-side 380px sliding drawer. Lists downloads sorted by: completed → in-progress → queued. Uses DownloadItem per entry.

**DownloadItem.vue**: Shows series name, episode number, phase text, progress bar, size info, server name, cancel/remove button.

### CSS / Design Tokens

**Global styles** (`style.css`):
- Background: `#0f0f0f`
- Text: `#e0e0e0`
- Primary accent: `#e94560` (red-ish)
- Success: `#27ae60`
- Secondary: `#333`
- All colors are HARDCODED hex values — no CSS variables defined
- The Wing Zero Custom palette from PROMPT.md is NOT yet applied

**Component-level colors** (all hardcoded):
- Navbar/Sidebar bg: `#1a1a2e`
- Sidebar border: `#e94560`
- Search input bg: `#16213e`
- Table header: `#1a1a2e`, th color: `#e94560`
- Card bg: `#1a1a1a`
- Trending card hover: `rgba(233, 69, 96, 0.2)` box-shadow
- Day group header border: `#e94560`
- En emisión header border: `#3498db`

**Plyr CSS variables** (in PlayerView only, unused):
- `--plyr-color-main: #e94560`

---

## 3. Android / Capacitor

### Configuration

**capacitor.config.json**:
```json
{
  "appId": "com.jkanime.gestor",
  "appName": "jkanime-vue",
  "webDir": "dist",
  "bundledWebRuntime": false,
  "plugins": { "SplashScreen": { "launchShowDuration": 0 } }
}
```

### Android Project (`frontend/android/`)
- Standard Capacitor Android project
- `namespace = "com.jkanime.gestor"`, `applicationId "com.jkanime.gestor"`
- SDK: minSdk/targetSdk from variables.gradle
- Dependencies: AppCompat, CoordinatorLayout, Core-SplashScreen, Capacitor
- Permissions: INTERNET only
- `launchMode="singleTask"` on MainActivity
- Splash screen via `@drawable/splash`

**strings.xml** (all need rebranding):
```xml
<string name="app_name">jkanime-vue</string>
<string name="title_activity_main">jkanime-vue</string>
<string name="package_name">com.jkanime.gestor</string>
<string name="custom_url_scheme">com.jkanime.gestor</string>
```

**styles.xml**: AppTheme with colorPrimary/colorPrimaryDark/colorAccent (references @color/ resources, values not inspected).

**Launcher icons**: Standard Capacitor icons in all mipmap densities — default purple Android icons, NOT custom branded.

### Build Process

**build-apk.bat**: 3-step pipeline:
1. `npm run build` (Vite)
2. `npx cap sync android`
3. `gradlew assembleDebug` (JDK 21 at hardcoded path)

Output: `android/app/build/outputs/apk/debug/app-debug.apk`

### Capacitor Integration in Frontend
- `main.js` detects Capacitor via dynamic import
- `config.js` store manages server URL via `@capacitor/preferences`
- `ConfigScreen.vue` shown on first launch (Capacitor only)
- All API calls use `configStore.baseUrl` for absolute URLs

---

## 4. Branding / Naming

### Current Name References (all need updating)

| File | Current Value | Field |
|---|---|---|
| `frontend/package.json` | `"name": "jkanime-vue"` | package name |
| `frontend/package-lock.json` | `"name": "jkanime-vue"` | package name |
| `frontend/index.html` | `<title>JKanime Gestor</title>` | page title |
| `frontend/capacitor.config.json` | `"appId": "com.jkanime.gestor"`, `"appName": "jkanime-vue"` | Capacitor config |
| `frontend/android/app/build.gradle` | `namespace = "com.jkanime.gestor"`, `applicationId "com.jkanime.gestor"` | Android identifiers |
| `frontend/android/.../strings.xml` | `app_name: "jkanime-vue"`, `package_name: "com.jkanime.gestor"` | Android strings |
| `frontend/android/.../capacitor.config.json` | Same as above (synced copy) | Synced asset |
| `frontend/src/components/AppNavbar.vue` | `<h1>JKanime Gestor</h1>` | Navbar brand text |
| `frontend/src/components/ConfigScreen.vue` | `<h2>JKanime Gestor</h2>` | Config screen title |
| `run.bat` | `title Jkanime Vue - Gestor de Series`, `echo` messages | Console title |
| `run.py` | `print("Jkanime Vue - Gestor de Series")` | Console output |
| `build-apk.bat` | `title Build APK - Jkanime Vue` | Console title |
| `backend/series/apps.py` | `verbose_name = 'Series JKanime'` | Admin verbose name |

### Logo Assets
- `backend/media/PI_Wing_Zero_Mercy.webp` — Official AnimeWing logo (webp format)
- `backend/media/logo.png` — Additional logo asset
- Android launcher icons: default Capacitor/Purple icons (NOT custom)
- No favicon configured
- No SVG icons in project

### CSS Variables (NOT yet defined — from PROMPT.md specification)
```css
:root {
  --bg-primary: #F7F8FC;      /* Blanco Pluma — 45% */
  --primary: #00539C;          /* Azul Cobalto — 25% */
  --text-main: #3A3D42;        /* Gris Grafito — 15% */
  --bg-secondary: #D18854;     /* Cobre Cálido — 10% */
  --accent-cta: #F4C430;       /* Amarillo V-Fin — 3% */
  --accent-subtle: #C8BFE7;    /* Púrpura Nebulosa — 2% */
  --text-muted: #6C757D;
  --border-light: #E2E8F0;
}
```

Current state: ALL of these are specified in PROMPT.md but ZERO are implemented in code. The app currently uses a dark theme (#0f0f0f bg, #e94560 red accent) while the spec calls for a light Wing Zero palette.

---

## 5. Build and Run

### run.bat (Full Setup)
1. Check/install Python (tries PATH, common install paths, winget)
2. Create virtualenv at `venv/`
3. `pip install -r requirements.txt`
4. `cd frontend && npm install && npm run build`
5. Launch `python run.py`

### run.py (Runtime)
1. Kill process on port 8000
2. Open browser to `http://127.0.0.1:8000`
3. Run `manage.py makemigrations` + `migrate`
4. Run `manage.py runserver 0.0.0.0:8000`
5. Workers start automatically via `AppConfig.ready()` (50 workers)

### Frontend Dev Mode
```
cd frontend && npm run dev
# Vite on port 5173, proxies /api → :8000, /media → :8000
```

### Vite Config (`vite.config.js`)
- Port: 5173
- Proxy: `/api` → `http://127.0.0.1:8000`, `/media` → `http://127.0.0.1:8000`
- Build output: `dist/`
- Plugins: `@vitejs/plugin-vue`

### Production Mode (run.py)
- Django serves `frontend/dist/index.html` for all non-API/non-asset routes (SPA fallback)
- Assets served from `frontend/dist/assets/` with hash-based caching
- Static files: `STATICFILES_DIRS` includes `frontend/dist`

### Dependencies
**Backend** (requirements.txt):
- django>=6.0, djangorestframework>=3.15, django-cors-headers>=4.4
- cloudscraper>=1.2.71, beautifulsoup4>=4.12.0
- requests>=2.31.0, Pillow>=10.0.0

**Frontend** (package.json):
- vue ^3.5.0, vue-router ^4.5.0, pinia ^3.0.0
- @capacitor/core ^8.4.2, @capacitor/android ^8.4.2, @capacitor/preferences ^8.0.1
- axios ^1.7.0, plyr ^3.8.4
- vite ^6.1.0, @vitejs/plugin-vue ^5.2.0

---

## 6. Key Findings for Implementation

### Critical Architecture Observations

1. **No CSS variables exist** — The entire Wing Zero palette from PROMPT.md needs to be created and applied. Currently ALL colors are hardcoded hex values.

2. **No extracted components for trending cards** — `trending-card` and `trending-grid` are inline scoped styles in `FavoritesView.vue`, not separate components. They'll need extraction.

3. **PlayerView.vue is dead code** — The route redirects to home. The actual player is `VideoPlayerModal.vue` (Teleported overlay). Don't confuse the two.

4. **50 workers, not 10** — `AppConfig.ready()` calls `start_workers(count=50)`. AGENTS.md says 10.

5. **No composables** — All API logic is inline in views. Pattern: direct API function imports + local ref state.

6. **Download progress overlay already exists** — `FavoritesView.vue` Tab 1 already has `dl-overlay` with spinner + progress bar + percentage for trending episodes. This is the pattern to reuse.

7. **No PWA manifest** — There's no `manifest.json` or PWA configuration.

8. **Android icons are defaults** — No custom launcher icons, no splash screen branding.

9. **Two duplicate prompt files** — `PROMPT.md` and `PROMPT2.md` are identical.

10. **The `/api/ultimos-episodios/` endpoint already enriches data** — Creates missing series/capitulos, replaces images with local portadas. Frontend tab grouping by `tab` field works.

### Files Affected by Rebranding

Every file listed in Section 4 needs name updates. Critical: the `applicationId` in `capacitor.config.json` and `build.gradle` is `com.jkanime.gestor` — changing this creates a NEW app identity on Android (users can't update, must reinstall).

### Files Affected by Wing Zero Palette

Every `.vue` component and `style.css` — ALL hardcoded colors need to become CSS variable references. This is a project-wide refactor touching every file in `frontend/src/`.

### Ready for Proposal

The exploration is complete. All areas documented. Ready for the proposal phase to break this into actionable implementation tasks.

---

## Affected Areas Summary

| Area | Key Files | Why |
|---|---|---|
| Rebranding | package.json, index.html, capacitor.config.json, build.gradle, strings.xml, AppNavbar.vue, ConfigScreen.vue, run.bat, run.py, build-apk.bat, apps.py | Name changes |
| Wing Zero palette | style.css, ALL .vue components, new :root variables | CSS variable migration |
| Component extraction | FavoritesView.vue → new TrendingCard.vue, TrendingGrid.vue | Reusable card components |
| Navigation state | FavoritesView.vue, router/index.js | Scroll/tab/group preservation |
| Android branding | icons/, strings.xml, styles.xml, splash | Custom icons + splash |
| Logo/favicon | index.html, Android resources | PI_Wing_Zero_Mercy.webp integration |
