# Trending Components Specification

## Purpose

Extract reusable `TrendingCard` and `TrendingGrid` components from inline styles in `FavoritesView.vue` so all three tabs share a consistent card+grid layout.

## Requirements

### Requirement: TrendingCard Component

The system SHALL provide `TrendingCard.vue` as a standalone component under `frontend/src/components/`.

**Props:**

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `image` | `String` | No | Image URL (fallback to placeholder) |
| `title` | `String` | Yes | Series/episode name |
| `subtitle` | `String` | No | Episode number, chapter count, or meta |
| `showFav` | `Boolean` | No | Show favorite heart button (default: `false`) |
| `isFavorite` | `Boolean` | No | Heart filled state (default: `false`) |
| `downloadState` | `Object` | No | `{ fase, porcentaje }` or `null` |

**Events:**

| Event | Payload | Description |
|-------|---------|-------------|
| `click` | — | Card body clicked (navigate to chapter/series) |
| `toggle-fav` | — | Favorite button clicked (stop propagation) |

**Slots:**

| Slot | Description |
|------|-------------|
| `overlay` | Custom overlay content (used for download progress) |

#### Scenario: Renders card with image and title

- GIVEN a TrendingCard with `image`, `title`, and `subtitle`
- WHEN the component renders
- THEN an `<img>` with the image URL displays
- AND the title text appears below
- AND the subtitle text appears below the title

#### Scenario: Shows download overlay when downloading

- GIVEN a TrendingCard with `downloadState` set to `{ fase: 'Descargando', porcentaje: 50 }`
- WHEN the component renders
- THEN a download overlay covers the image
- AND the overlay shows the phase text
- AND the overlay shows a progress bar at 50%
- AND the overlay shows "50%" text

#### Scenario: Shows placeholder for missing image

- GIVEN a TrendingCard with no `image` prop
- WHEN the component renders
- THEN a placeholder element displays with "Sin portada" text

#### Scenario: Favorite button emits on click

- GIVEN a TrendingCard with `showFav="true"`
- WHEN the user clicks the heart button
- THEN a `toggle-fav` event emits
- AND the card body `click` event does NOT emit

### Requirement: TrendingGrid Component

The system SHALL provide `TrendingGrid.vue` as a layout wrapper under `frontend/src/components/`.

**Props:**

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `minCardWidth` | `Number` | No | Minimum card width in px (default: `160`) |
| `gap` | `Number` | No | Grid gap in px (default: `16`) |

**Slots:**

| Slot | Description |
|------|-------------|
| `default` | Card content (TrendingCard instances) |

#### Scenario: Renders responsive grid

- GIVEN a TrendingGrid with 6 TrendingCard children
- WHEN the container is 800px wide
- THEN cards display in a grid with columns adapting to `minCardWidth`
- AND gap between cards matches the `gap` prop

#### Scenario: Empty grid renders nothing

- GIVEN a TrendingGrid with no slot content
- WHEN it renders
- THEN no DOM elements are produced beyond the grid container

### Requirement: Tab Integration

The three tabs in `FavoritesView.vue` SHALL use TrendingCard and TrendingGrid:

- **Últimos episodios**: TrendingCard with `image`, `title`, `subtitle` (episode number), `downloadState` (overlay), no `showFav`
- **En emisión**: TrendingCard with `image`, `title`, `subtitle` (chapter count), `showFav`, `isFavorite`
- **Concluidos**: TrendingCard with `image`, `title`, `subtitle` (downloaded/total), `showFav`, `isFavorite`

#### Scenario: All three tabs use extracted components

- GIVEN FavoritesView renders each tab
- WHEN DOM is inspected
- THEN each tab's card grid uses `<TrendingGrid>` and `<TrendingCard>` components
- AND no inline card markup or scoped card styles remain in FavoritesView.vue

#### Scenario: Download overlay renders in Últimos tab

- GIVEN an episode is downloading in the Últimos episodios tab
- WHEN the TrendingCard renders
- THEN the download overlay shows spinner, phase, progress bar, and percentage
