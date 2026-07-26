# Design: Testing Infrastructure

## Technical Approach

Add Vitest (frontend) and pytest-django (backend) test runners to a project that currently has zero test infrastructure. Also generate PWA icons from the existing logo. The design follows the project's existing conventions: Vite config for frontend, Django settings for backend, no CI/CD yet. Three specs guide implementation: `frontend-testing/spec.md`, `backend-testing/spec.md`, `pwa-icons/spec.md`.

## Architecture Decisions

| Decision | Choice | Alternatives | Rationale |
|----------|--------|-------------|-----------|
| Frontend runner | Vitest 3.x in `vite.config.js` test block | Jest standalone | Vitest shares Vite's transform pipeline — zero config duplication with existing Vite 6 build |
| Test environment | jsdom | happy-dom | jsdom is spec-compliant and matches `@testing-library/jest-dom` expectations; happy-dom is faster but less complete |
| Globals | `test.globals: true` | Explicit imports per file | Matches Jest convention; reduces boilerplate in every test file |
| Setup file | `tests/setup.js` imports `@testing-library/jest-dom/vitest` | Inline matchers | Single source of truth for DOM matchers; referenced via `test.setupFiles` |
| Backend runner | pytest + pytest-django with `pytest.ini` | Django's `manage.py test` | pytest has better fixtures, markers, and output; `pytest.ini` over `pyproject.toml` because project has no `pyproject.toml` yet |
| Test DB | In-memory SQLite via `pytest-django` `@pytest.mark.django_db` | TransactionTestCase | Faster; no disk I/O; sufficient for unit/model tests |
| Test structure (backend) | `series/tests/` package (`test_models.py`, `test_api.py`) | Single `tests.py` | Per-spec requirement; keeps model tests separate from endpoint tests |
| Icon generation | Python PIL/Pillow script (single-use) | sharp/Node | Backend already imports PIL (views.py lines 21, 397, 674); no new dependency needed |
| Icon source | `backend/media/PI_Wing_Zero_Mercy.webp` (also at `frontend/public/`) | Separate source | Source exists in both locations; the `public/` copy is already there |

## Data Flow

### Test Execution

```
npx vitest run (frontend/)
  └─→ vite.config.js test block
        ├─→ setup.js (jest-dom matchers)
        ├─→ tests/unit/ (stores, API)
        └─→ tests/component/ (TrendingCard, TrendingGrid)

python -m pytest (backend/)
  └─→ pytest.ini
        ├─→ conftest.py (fixtures, DB setup)
        ├─→ series/tests/test_models.py (Serie, Capitulo)
        └─→ series/tests/test_api.py (ultimos-episodios endpoint)
```

### Icon Generation

```
backend/media/PI_Wing_Zero_Mercy.webp
  └─→ Python PIL script
        ├─→ frontend/public/icon-192.png (192x192)
        ├─→ frontend/public/icon-512.png (512x512)
        └─→ frontend/public/manifest.json (updated icons array)
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `frontend/vite.config.js` | Modify | Add `test` block: `globals: true`, `environment: 'jsdom'`, `setupFiles: ['./tests/setup.js']` |
| `frontend/package.json` | Modify | Add devDependencies: `vitest`, `@testing-library/vue`, `@testing-library/jest-dom`, `jsdom` |
| `frontend/tests/setup.js` | Create | Imports `@testing-library/jest-dom/vitest` for DOM matchers |
| `frontend/tests/unit/config-store.test.js` | Create | Tests: defaults (`host`, `port`), `baseUrl` getter, `saveConfig` persists values |
| `frontend/tests/unit/favorites-store.test.js` | Create | Tests: `setFavorito` add/remove, `loadFromSeries` population |
| `frontend/tests/unit/api.test.js` | Create | Tests: `getVideoUrl`, `getGuardarProgresoUrl` URL construction with mocked config store |
| `frontend/tests/component/TrendingCard.test.js` | Create | Tests: renders title, shows placeholder when no image, emits click |
| `frontend/tests/component/TrendingGrid.test.js` | Create | Tests: renders slot content, applies CSS grid variables |
| `backend/pytest.ini` | Create | `DJANGO_SETTINGS_MODULE = config.settings`, `testpaths = series/tests` |
| `backend/conftest.py` | Create | `client` fixture (Django test client); shared test utilities |
| `backend/series/tests/__init__.py` | Create | Empty; makes `tests/` a Python package |
| `backend/series/tests/test_models.py` | Create | Tests: `Serie.__str__`, slug auto-generation from URL, `estado` choices; `Capitulo.__str__`, `archivo_existe` (file exists/missing), `nombre_archivo` |
| `backend/series/tests/test_api.py` | Create | Tests: `api_ultimos_episodios` 200 status, empty list when no episodes |
| `frontend/public/icon-192.png` | Create | Generated 192x192 PNG from webp source |
| `frontend/public/icon-512.png` | Create | Generated 512x512 PNG from webp source |
| `frontend/public/manifest.json` | Modify | Add PNG icon entries with `purpose: "any maskable"` alongside existing webp entry |

## Interfaces / Contracts

### Vitest Config Addition (vite.config.js)

```js
// Added to existing defineConfig export
test: {
  globals: true,
  environment: 'jsdom',
  setupFiles: ['./tests/setup.js'],
}
```

### pytest.ini

```ini
[pytest]
DJANGO_SETTINGS_MODULE = config.settings
python_files = tests.py test_*.py *_tests.py
python_classes = Test*
python_functions = test_*
testpaths = series/tests
```

### Pinia Store Test Pattern

```js
// Every store test: createPinia + setActivePinia before each test
import { createPinia, setActivePinia } from 'pinia'
beforeEach(() => { setActivePinia(createPinia()) })
```

### Config Store Mock (for API tests)

```js
// Mock @capacitor/preferences to prevent native API calls
vi.mock('@capacitor/preferences', () => ({
  Preferences: { get: vi.fn(), set: vi.fn(), remove: vi.fn() },
}))
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit (frontend) | Config store defaults, save/load, baseUrl getter | Vitest + Pinia `setActivePinia`; mock `@capacitor/preferences` |
| Unit (frontend) | Favorites store toggle, loadFromSeries | Vitest + Pinia; no external deps |
| Unit (frontend) | API URL construction (getVideoUrl, getGuardarProgresoUrl) | Vitest; mock config store with `vi.mock` |
| Component (frontend) | TrendingCard render, props, events | `@testing-library/vue` `mount()`; assert DOM output |
| Component (frontend) | TrendingGrid slot rendering | `@testing-library/vue` `mount()` with child content |
| Unit (backend) | Serie model: __str__, slug generation, choices | pytest + `@pytest.mark.django_db`; create/save instances |
| Unit (backend) | Capitulo model: __str__, archivo_existe, nombre_archivo | pytest + `@pytest.mark.django_db`; mock `os.path.isfile` for archivo_existe |
| Integration (backend) | api_ultimos_episodios endpoint returns 200 | pytest + Django test client; mock scraper to avoid network |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary.

## Migration / Rollout

No migration required. This is pure infrastructure addition:
- New devDependencies in `frontend/package.json`
- New test files and directories (no existing code deleted)
- New `pytest.ini` and `conftest.py` (no existing config overwritten)
- Generated icon PNGs added to `frontend/public/` (no existing files modified)
- `manifest.json` augmented with additional icon entries (webp entry preserved)

Existing `npm run build` and Django `runserver` remain unaffected — test files are outside `src/` and `dist/` pipelines.

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| No existing test patterns to follow | This change establishes conventions; design decisions document the chosen patterns |
| `@capacitor/preferences` crashes in jsdom | Mock module in every test that touches config store |
| Django DB tests need isolation | `pytest-django` `@pytest.mark.django_db` uses transaction rollback per test |
| Icon conversion needs PIL/Pillow | Already installed — `backend/series/views.py` imports `from PIL import Image` (line 21) |
| Vitest 3.x / Vite 6 compatibility | Vitest 3.x is designed for Vite 6; pin `vitest: ^3.0.0` |

## Open Questions

- [ ] Should component tests go in `tests/component/` (singular, per spec) or `tests/components/` (plural, per proposal)? **Design follows spec**: `tests/component/`.
- [ ] The `api_ultimos_episodios` endpoint calls a live scraper — test must mock `get_scraper("jkanime")` to avoid network dependency. Confirm this is acceptable for initial tests.
