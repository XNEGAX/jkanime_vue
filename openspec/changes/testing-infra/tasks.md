# Tasks: Testing Infrastructure

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~730 (config ~80, frontend tests ~350, backend tests + icons ~300) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 (infra) → PR 2 (frontend tests) → PR 3 (backend tests + PWA icons) |
| Delivery strategy | ask-on-risk |
| Chain strategy | stacked-to-main |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Test infrastructure config + setup files | PR 1 | `cd frontend && npx vitest run` (empty pass); `cd backend && python -m pytest --co` (collection only) | N/A — no real tests yet, validates runner boots | Revert vite.config.js, package.json, pytest.ini, conftest.py, setup.js |
| 2 | Frontend unit + component tests | PR 2 | `cd frontend && npx vitest run` | Real: Vitest + jsdom + Pinia | Remove `frontend/tests/` directory; revert package.json devDeps |
| 3 | Backend tests + PWA icons | PR 3 | `cd backend && python -m pytest` | Real: pytest + Django test client + in-memory SQLite | Remove `backend/series/tests/`, pytest.ini, conftest.py, icon PNGs, manifest changes |

## Phase 1: Infrastructure & Configuration

- [ ] 1.1 Add devDependencies to `frontend/package.json`: `vitest ^3.0.0`, `@testing-library/vue`, `@testing-library/jest-dom`, `jsdom`
- [ ] 1.2 Add `test` block to `frontend/vite.config.js`: `globals: true`, `environment: 'jsdom'`, `setupFiles: ['./tests/setup.js']`
- [ ] 1.3 Create `frontend/tests/setup.js` — imports `@testing-library/jest-dom/vitest`
- [ ] 1.4 Create `frontend/tests/unit/` and `frontend/tests/component/` directories (with `.gitkeep`)
- [ ] 1.5 Add `pytest` and `pytest-django` to backend dependencies (`requirements.txt` or equivalent)
- [ ] 1.6 Create `backend/pytest.ini` — `DJANGO_SETTINGS_MODULE = config.settings`, `testpaths = series/tests`
- [ ] 1.7 Create `backend/conftest.py` — `client` fixture (Django test client), in-memory SQLite marker
- [ ] 1.8 Create `backend/series/tests/__init__.py` (empty)

## Phase 2: Frontend Tests

- [ ] 2.1 Create `frontend/tests/unit/config-store.test.js` — defaults (`host`, `port`), `setConfig` persistence to localStorage (mock `@capacitor/preferences`)
- [ ] 2.2 Create `frontend/tests/unit/favorites-store.test.js` — `toggle` add/remove, `loadFromSeries` population
- [ ] 2.3 Create `frontend/tests/unit/api.test.js` — `getVideoUrl` and `getGuardarProgresoUrl` URL construction (mock config store + axios)
- [ ] 2.4 Create `frontend/tests/component/TrendingCard.test.js` — renders title, placeholder when no image, emits click event
- [ ] 2.5 Create `frontend/tests/component/TrendingGrid.test.js` — renders slot content, applies CSS grid variables
- [ ] 2.6 Run `cd frontend && npx vitest run` — verify 0 errors, all tests green

## Phase 3: Backend Tests

- [ ] 3.1 Create `backend/series/tests/test_models.py` — `Serie.__str__`, slug auto-generation from nombre, `estado` choices validity
- [ ] 3.2 Create `backend/series/tests/test_models.py` — `Capitulo.__str__`, `archivo_existe` (mock `os.path.isfile` for True/False), `nombre_archivo`
- [ ] 3.3 Create `backend/series/tests/test_api.py` — `api_ultimos_episodios` returns 200 + non-empty list (seed data)
- [ ] 3.4 Create `backend/series/tests/test_api.py` — `api_ultimos_episodios` returns 200 + empty list (no episodes)
- [ ] 3.5 Run `cd backend && python -m pytest -v` — verify 0 errors, all tests green

## Phase 4: PWA Icons

- [ ] 4.1 Write one-off Python script to convert `backend/media/PI_Wing_Zero_Mercy.webp` → `frontend/public/icon-192.png` (192x192) and `icon-512.png` (512x512) using PIL/Pillow
- [ ] 4.2 Run the script, verify both PNGs exist with correct dimensions
- [ ] 4.3 Update `frontend/public/manifest.json` — add icon entries: `{ "src": "/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable" }` and same for 512x512
- [ ] 4.4 Run `cd frontend && npm run build` — verify build passes, PNGs copied to `dist/`
