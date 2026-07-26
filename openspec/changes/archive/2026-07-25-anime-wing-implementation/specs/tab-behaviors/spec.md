# Tab Behaviors Specification

## Purpose

Define the click-to-play, grouping, and search behaviors for the three FavoritesView tabs, including the backend-frontend flow for trending episodes and the filtering logic for En emisión and Concluidos.

## Requirements

### Requirement: Ultimos Episodios Click-to-Play

The system SHALL handle clicks on trending episode cards using the ChaptersView play flow:

1. If the episode has no `capitulo_id`, navigate to the series chapters view (`/serie/{serie_id}`) or open the source URL as fallback.
2. If the episode has a `capitulo_id`, call `verificarCapitulo` to check file validity.
3. If valid, open `VideoPlayerModal` with the `capitulo_id`.
4. If invalid or missing, call `descargarCapitulo`, show download overlay on the card, and auto-play on completion.

#### Scenario: Episode with capitulo_id plays directly

- GIVEN a trending episode with `capitulo_id: 42` and a valid local MP4
- WHEN the user clicks the card
- THEN `verificarCapitulo(42)` is called
- AND on `valido: true`, `VideoPlayerModal` opens with capituloId 42

#### Scenario: Episode downloads then plays

- GIVEN a trending episode with `capitulo_id: 42` and no local file
- WHEN the user clicks the card
- THEN `verificarCapitulo(42)` returns `valido: false`
- AND `descargarCapitulo(42)` is called
- AND a download overlay appears on the card showing progress
- AND when the download completes, `VideoPlayerModal` opens

#### Scenario: Episode with no capitulo_id navigates to chapters

- GIVEN a trending episode with `capitulo_id: null` and `serie_id: 7`
- WHEN the user clicks the card
- THEN the router navigates to `/serie/7`

#### Scenario: Episode with no capitulo_id and no serie_id opens URL

- GIVEN a trending episode with `capitulo_id: null` and `serie_id: null`
- WHEN the user clicks the card
- THEN `window.open(ep.url, '_blank')` opens the source page

### Requirement: Download Overlay on Card

The system SHALL display a download progress overlay on trending cards when an episode download is active.

#### Scenario: Active download shows overlay

- GIVEN a trending card for `capituloId: 42`
- WHEN `dlStore` has a matching entry with state `PROGRESS`
- THEN the card image is covered by a dark overlay
- AND the overlay shows: spinner, phase text, progress bar, and percentage

#### Scenario: No active download hides overlay

- GIVEN a trending card for `capituloId: 42`
- WHEN no download entry exists or download state is `SUCCESS`
- THEN no overlay is visible

### Requirement: En Emision Chronological Grouping

The "En emisión" tab SHALL group favorite series by `dia_emision`, ordered from today backwards (most recent day first).

#### Scenario: Groups ordered from today

- GIVEN today is Wednesday (index 2)
- WHEN the En emisión tab renders
- THEN groups display in order: Miércoles, Martes, Lunes, Domingo, Sábado, Viernes, Jueves

#### Scenario: Empty days are hidden

- GIVEN no series air on Thursday
- WHEN the En emisión tab renders
- THEN the Jueves group is not displayed

#### Scenario: Search filters within tab

- GIVEN the user types "naruto" in the search input
- WHEN the En emisión tab renders
- THEN only series whose `nombre` contains "naruto" (case-insensitive) are shown
- AND empty groups after filtering are hidden

### Requirement: Concluidos Alphabetical Grouping

The "Concluidos" tab SHALL group favorite series by the first letter of `nombre`, sorted alphabetically, with search filtering.

#### Scenario: Groups by first letter

- GIVEN concluidas series: "Bleach", "Naruto", "Attack on Titan", "Nana"
- WHEN the Concluidos tab renders
- THEN groups display as: A (1), B (1), N (2)

#### Scenario: Search filters within tab

- GIVEN the user types "naruto" in the search input
- WHEN the Concluidos tab renders
- THEN only series matching "naruto" appear
- AND groups with no matching series are hidden

#### Scenario: Shows download counts

- GIVEN a concluida series with 12 chapters and 8 downloaded
- WHEN the card renders
- THEN the subtitle shows "8/12 descargados"
