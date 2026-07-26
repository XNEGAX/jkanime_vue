# Backend: /api/ultimos-episodios/ Enrichment Specification

## Purpose

Verify and document the existing enrichment logic in `series/views.py` (`api_ultimos_episodios`), ensuring the response format is complete and consistent for the frontend trending tabs.

## Requirements

### Requirement: Series Auto-Creation

The endpoint SHALL create a new `Serie` record when a trending episode references a slug not present in the database. The series SHALL be created with:

- `nombre` from the scraped episode name
- `slug` parsed from the episode URL
- `fuente = "jkanime"`
- `portada` downloaded from the CDN (`cdn.jkdesa.com/assets/images/animes/image/{slug}.jpg`) with fallback to scraped image

#### Scenario: New series created from trending episode

- GIVEN a trending episode with slug `mi-anime`
- WHEN `mi-anime` does not exist in the Serie table
- THEN a new Serie record is created with `nombre`, `slug`, `fuente="jkanime"`
- AND the portada is downloaded from CDN (or scraped fallback)

#### Scenario: Existing series is reused

- GIVEN a trending episode with slug `mi-anime`
- WHEN `mi-anime` already exists in the Serie table
- THEN no duplicate Serie is created
- AND the existing series' portada is used for the image replacement

### Requirement: Capitulo Auto-Creation

The endpoint SHALL create a `Capitulo` record when a trending episode has a numeric `episodio` value not present for that series.

#### Scenario: New chapter created

- GIVEN a trending episode with `episodio: 5` for an existing series
- WHEN no Capitulo with `numero=5` exists for that series
- THEN a new Capitulo is created with `numero=5` and `url_fuente` from the scraped URL

#### Scenario: Existing chapter is reused

- GIVEN a trending episode with `episodio: 5`
- WHEN a Capitulo with `numero=5` already exists
- THEN the existing Capitulo is used (no duplicate)

### Requirement: Image Replacement

The endpoint SHALL replace the scraped `imagen` URL with the local `portada.url` when the series has a locally stored cover image.

#### Scenario: Local portada replaces CDN image

- GIVEN a trending episode for a series that has `serie.portada` set
- WHEN the response is assembled
- THEN `ep["imagen"]` equals `serie.portada.url` (the local media URL)

#### Scenario: No portada preserves scraped image

- GIVEN a trending episode for a series without `serie.portada`
- WHEN the response is assembled
- THEN `ep["imagen"]` preserves the original scraped URL

### Requirement: Response Format

The endpoint SHALL return a JSON response with this exact structure:

```json
{
  "nombre": "Últimos episodios",
  "episodios": [
    {
      "nombre": "...",
      "episodio": "...",
      "imagen": "...",
      "url": "...",
      "tab": "Animes|Donghuas|Ovas",
      "serie_id": 123,
      "capitulo_id": 456,
      "archivo_existe": false
    }
  ],
  "total": 15
}
```

The `serie_id`, `capitulo_id`, and `archivo_existe` fields are added by the enrichment logic and MUST be present in every episode object.

#### Scenario: Enrichment fields are always present

- GIVEN the endpoint returns trending episodes
- WHEN the JSON response is parsed
- THEN every episode object contains `serie_id`, `capitulo_id`, and `archivo_existe` keys
- AND `serie_id` is an integer or null
- AND `capitulo_id` is an integer or null

#### Scenario: No series match returns null IDs

- GIVEN a trending episode whose URL cannot be parsed to a valid slug
- WHEN enrichment runs
- THEN `serie_id` is `null` and `capitulo_id` is `null`
