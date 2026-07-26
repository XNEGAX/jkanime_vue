# Frontend Testing Specification

## Purpose

Establish Vitest as the frontend test runner with @testing-library/vue for component testing, jsdom as the browser environment, and an initial test suite covering critical Pinia stores and API utility functions.

## Requirements

### Requirement: Vitest Runner Configuration

The project SHALL configure Vitest within the existing `vite.config.js` file, adding a `test` block that sets `globals: true`, `environment: 'jsdom'`, and references a setup file for jest-dom matchers.

#### Scenario: Vitest runs with correct environment

- GIVEN `vite.config.js` contains a `test` block with `environment: 'jsdom'`
- WHEN `npx vitest run` is executed from `frontend/`
- THEN the process exits with code 0
- AND tests run against a jsdom DOM environment

#### Scenario: Globals are enabled without explicit imports

- GIVEN `vite.config.js` sets `test.globals = true`
- WHEN a test file uses `describe`, `it`, `expect` without importing them
- THEN the test compiles and runs without import errors

### Requirement: Jest-DOM Matchers Setup

The project SHALL provide a setup file (e.g., `tests/setup.js`) that imports `@testing-library/jest-dom/vitest`. This file MUST be referenced in the `test.setupFiles` array in `vite.config.js`.

#### Scenario: DOM matchers available in all tests

- GIVEN the setup file is configured in `vite.config.js`
- WHEN a test uses `expect(element).toBeInTheDocument()`
- THEN the matcher resolves without `TypeError`

### Requirement: Test Directory Structure

The project SHALL organize tests under `frontend/tests/` with two subdirectories: `unit/` for pure logic tests and `component/` for @testing-library/vue rendered tests.

#### Scenario: Unit tests exist for stores and API

- GIVEN `tests/unit/` contains `config-store.test.js`, `favorites-store.test.js`, `api.test.js`
- WHEN `npx vitest run tests/unit/` is executed
- THEN all test files are discovered and executed

#### Scenario: Component tests directory is created

- GIVEN `tests/component/` exists
- WHEN `npx vitest run tests/component/` is executed
- THEN the runner discovers and runs any test files in that directory

### Requirement: Config Store Coverage

Tests SHALL verify the `config` Pinia store's `host`, `port`, `baseUrl` getter, and that `setConfig` persists values to localStorage.

#### Scenario: Default config values

- GIVEN a fresh config store (no localStorage)
- WHEN the store is initialized
- THEN `host` defaults to `"127.0.0.1"`
- AND `port` defaults to `"8000"`

#### Scenario: setConfig persists to localStorage

- GIVEN a config store instance
- WHEN `setConfig({ host: "192.168.1.1", port: "3000" })` is called
- THEN `host` equals `"192.168.1.1"`
- AND `port` equals `"3000"`
- AND localStorage contains the updated values

### Requirement: Favorites Store Coverage

Tests SHALL verify `toggle` (add/remove) and `loadFromSeries` behavior on the `favorites` Pinia store.

#### Scenario: Toggle adds a series

- GIVEN the favorites store is empty
- WHEN `toggle(seriesId)` is called with id `"abc"`
- THEN the series id is present in the store

#### Scenario: Toggle removes an existing series

- GIVEN the favorites store contains `"abc"`
- WHEN `toggle("abc")` is called
- THEN the series id is no longer in the store

#### Scenario: loadFromSeries populates store from array

- GIVEN a list of series objects with `_id` fields
- WHEN `loadFromSeries(seriesList)` is called
- THEN all `_id` values are present in the store

### Requirement: API Function Coverage

Tests SHALL verify `getVideoUrl` and `getGuardarProgresoUrl` return correctly formatted URLs given host, port, and path parameters. Axios calls MUST be mocked.

#### Scenario: getVideoUrl returns correct URL

- GIVEN config host `"127.0.0.1"` and port `"8000"`
- WHEN `getVideoUrl("my-slug", 5)` is called
- THEN the returned URL contains `/api/video/my-slug/5`

#### Scenario: getGuardarProgresoUrl returns correct URL

- GIVEN config host `"127.0.0.1"` and port `"8000"`
- WHEN `getGuardarProgresoUrl("my-slug", 10)` is called
- THEN the returned URL contains `/api/guardar-progreso/my-slug/10`
