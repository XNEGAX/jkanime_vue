# Backend Testing Specification

## Purpose

Establish pytest with pytest-django as the backend test runner, provide shared fixtures via conftest.py, and create an initial test suite covering the `Serie` and `Capitulo` models and the `api_ultimos_episodios` endpoint.

## Requirements

### Requirement: Pytest Configuration

The project SHALL include a `pytest.ini` (or equivalent `pyproject.toml` section) in `backend/` that sets `DJANGO_SETTINGS_MODULE = config.settings` and defines `testpaths = series/tests`.

#### Scenario: Pytest discovers tests on default invocation

- GIVEN `pytest.ini` exists in `backend/` with the correct `DJANGO_SETTINGS_MODULE`
- WHEN `python -m pytest` is run from `backend/`
- THEN all test files under `series/tests/` are discovered
- AND the Django settings module is loaded without `ImportError`

### Requirement: Shared Test Fixtures (conftest.py)

The project SHALL provide `backend/conftest.py` with a `client` fixture (Django test client) and a `db` marker that uses an in-memory SQLite database for speed.

#### Scenario: Test client fixture is available

- GIVEN `conftest.py` defines a `client` fixture
- WHEN a test function accepts `client` as a parameter
- THEN the fixture returns a `django.test.Client` instance
- AND the database is in-memory (not on disk)

### Requirement: Serie Model Coverage

Tests SHALL verify the `Serie` model's `__str__`, `slug` auto-generation, and `estado`/`dia_emision` field choices.

#### Scenario: Serie __str__ returns nombre

- GIVEN a `Serie` instance with `nombre = "Sword Art Online"`
- WHEN `str(serie)` is called
- THEN the result equals `"Sword Art Online"`

#### Scenario: Slug is auto-generated from nombre

- GIVEN a new `Serie` with `nombre = "Naruto Shippuden"` and no explicit `slug`
- WHEN the instance is saved to the database
- THEN `serie.slug` is populated (non-empty, URL-safe)

#### Scenario: Estado field accepts valid choices

- GIVEN a `Serie` with `estado = "Emision"`
- WHEN the instance is saved
- THEN no `ValidationError` is raised

### Requirement: Capitulo Model Coverage

Tests SHALL verify the `Capitulo` model's `__str__`, `archivo_existe` method, and `nombre_archivo` field behavior.

#### Scenario: Capitulo __str__ returns formatted string

- GIVEN a `Capitulo` with `numero = 1` belonging to a `Serie` named "Bleach"
- WHEN `str(capitulo)` is called
- THEN the result includes the number and serie name

#### Scenario: archivo_existe returns True when file exists

- GIVEN a `Capitulo` with a valid `archivo_existe` pointing to an existing file
- WHEN `capitulo.archivo_existe()` is called
- THEN the method returns `True`

#### Scenario: archivo_existe returns False when file missing

- GIVEN a `Capitulo` with a `archivo_existe` path that does not exist on disk
- WHEN `capitulo.archivo_existe()` is called
- THEN the method returns `False`

### Requirement: API Endpoint Coverage

Tests SHALL verify the `api_ultimos_episodios` endpoint returns a 200 status and a list of episodes ordered by recency.

#### Scenario: Endpoint returns 200 with episode list

- GIVEN at least one `Capitulo` exists in the database
- WHEN a GET request is sent to `/api/ultimos-episodios/`
- THEN the response status is `200`
- AND the response body contains a non-empty list

#### Scenario: Endpoint returns empty list when no episodes exist

- GIVEN no `Capitulo` records exist in the database
- WHEN a GET request is sent to `/api/ultimos-episodios/`
- THEN the response status is `200`
- AND the response body is an empty list

### Requirement: Test Module Structure

The project SHALL place all backend tests under `backend/series/tests/` as a Python package with `__init__.py`, organizing tests into `test_models.py` and `test_api.py`.

#### Scenario: Tests are organized by concern

- GIVEN `series/tests/test_models.py` and `series/tests/test_api.py` exist
- WHEN `python -m pytest series/tests/` is run
- THEN model tests run from `test_models.py`
- AND endpoint tests run from `test_api.py`
