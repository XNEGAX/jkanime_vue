# Proposal: Testing Infrastructure

## Intent

The project has zero test infrastructure — no test runner, no test config, no test files. This makes refactoring risky, regressions invisible, and onboarding slower. Adding Vitest (frontend) and pytest (backend) establishes a safety net and enables TDD going forward. PWA icons are bundled as a small unrelated deliverable to avoid a separate change.

## Scope

### In Scope
- **Frontend**: Vitest + @testing-library/vue + jsdom setup, initial unit/component tests
- **Backend**: pytest + pytest-django setup, initial model/API tests
- **PWA icons**: Generate 192x192 and 512x512 PNGs from existing `backend/media/PI_Wing_Zero_Mercy.webp`, add to `frontend/public/`

### Out of Scope
- E2E tests (Playwright/Cypress) — deferred
- CI/CD pipeline integration — deferred
- 100% coverage — this sets the foundation, not the ceiling
- Android mipmap resource generation (Capacitor handles this)

## Capabilities

### New Capabilities
- `frontend-testing`: Vitest config, test utilities, initial unit tests for stores and API functions
- `backend-testing`: pytest config, fixtures, initial model and API endpoint tests

### Modified Capabilities
None — pure infrastructure addition, no existing spec behavior changes.

## Approach

### Frontend (Vitest)
- Add `vitest`, `@testing-library/vue`, `@testing-library/jest-dom`, `jsdom` as devDependencies
- Extend `vite.config.js` with `test` block (globals, environment, setup files)
- Create `frontend/tests/unit/` and `frontend/tests/components/` directories
- Initial tests: `config` store (actions/getters), `favorites` store, `api/index.js` (mocked axios)

### Backend (pytest)
- Add `pytest`, `pytest-django` to dependencies
- Create `backend/pytest.ini` with `DJANGO_SETTINGS_MODULE` and test paths
- Create `backend/conftest.py` with shared fixtures (DB setup, test client)
- Initial tests: `Serie` model (str, slug generation, choices), `Capitulo` model (str, archivo_existe), `api_ultimos_episodios` endpoint

### PWA Icons
- Use sharp/canvas or PIL script to convert `PI_Wing_Zero_Mercy.webp` → 192x192 + 512x512 PNGs
- Place in `frontend/public/icon-192.png` and `frontend/public/icon-512.png`
- Update `manifest.json` references if present

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `frontend/vite.config.js` | Modified | Add `test` configuration block |
| `frontend/package.json` | Modified | New devDependencies (vitest, testing-library) |
| `frontend/tests/` | New | Test directory structure + initial test files |
| `backend/pytest.ini` | New | pytest configuration |
| `backend/conftest.py` | New | Shared test fixtures |
| `backend/series/tests.py` | Modified | Replace empty stub with real tests |
| `frontend/public/` | New | PWA icon PNGs |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Vitest version conflicts with Vite 6 | Low | Vitest 3.x is designed for Vite 6 — pin compatible versions |
| pytest-django SQLite lock contention | Low | Use in-memory SQLite test DB via settings override |
| PWA icon quality loss from .webp→PNG | Low | Source image is high-res; bilinear downscale is fine |

## Rollback Plan

- **Frontend**: Remove `tests/` dir, revert `vite.config.js` changes, uninstall vitest packages
- **Backend**: Delete `pytest.ini` + `conftest.py`, revert `tests.py` to empty stub
- **PWA**: Remove PNGs from `frontend/public/`

## Dependencies

- Vite 6 (already installed) — Vitest 3.x is the compatible version
- Django 6 (already installed) — pytest-django 4.x compatible

## Success Criteria

- [ ] `cd frontend && npx vitest run` passes with 0 errors
- [ ] `cd backend && python -m pytest` passes with 0 errors
- [ ] Initial frontend tests cover: config store, favorites store, API base URL logic
- [ ] Initial backend tests cover: Serie model, Capitulo model, ultimos-episodios endpoint
- [ ] PWA icons present at `frontend/public/icon-{192,512}.png`
- [ ] Existing build (`npm run build`) unaffected
