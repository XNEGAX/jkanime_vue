# Navigation State Specification

## Purpose

Preserve user navigation state (scroll position, selected tab, expanded group) when navigating away from FavoritesView and returning via browser back.

## Requirements

### Requirement: Scroll Position Preservation

The system SHALL save the scroll position of the FavoritesView main container to `sessionStorage` on route leave and restore it on route re-enter.

#### Scenario: Back-navigation restores scroll position

- GIVEN the user scrolls to the third day-group in the "En emisión" tab
- WHEN they navigate to a series detail page
- AND press browser back
- THEN the page scrolls to the exact same position (±20px tolerance)

#### Scenario: New session starts at top

- GIVEN a fresh browser session (no sessionStorage)
- WHEN the user navigates to /favoritos
- THEN the page scrolls to the top

### Requirement: Tab State Preservation

The system SHALL persist the active tab key to `sessionStorage` and restore it on re-entry.

#### Scenario: Back-navigation restores active tab

- GIVEN the user is on the "Concluidos" tab
- WHEN they navigate to /serie/5 and press back
- THEN the "Concluidos" tab is active (not the default "Últimos episodios")

#### Scenario: Tab key is invalid on restore

- GIVEN sessionStorage has `animewing-fav-tab` = "invalid_value"
- WHEN FavoritesView mounts
- THEN the active tab defaults to "ultimos"

### Requirement: Group/Section State Preservation

The system SHALL preserve the expanded group or scroll-anchor context for the current tab.

#### Scenario: Day-group scroll anchor preserved

- GIVEN the user is scrolled to the "Viernes" day-group in "En emisión"
- WHEN they navigate away and press back
- THEN the scroll position targets the "Viernes" group header

#### Scenario: Alphabetical group anchor preserved in Concluidos

- GIVEN the user is at the "M" letter group in "Concluidos"
- WHEN they navigate away and press back
- THEN scroll restores near the "M" group header

### Requirement: Router ScrollBehavior Integration

The router SHALL define a `scrollBehavior` function in `frontend/src/router/index.js` that coordinates with sessionStorage.

#### Scenario: scrollBehavior reads sessionStorage for /favoritos

- GIVEN sessionStorage has saved scroll state for /favoritos
- WHEN the router resolves a navigation back to /favoritos
- THEN `scrollBehavior` returns the saved `{ top, left }` value

#### Scenario: scrollBehavior returns default for other routes

- GIVEN any navigation to routes other than /favoritos
- WHEN `scrollBehavior` is called
- THEN it returns `{ top: 0 }` (or the hash anchor if present)

### Requirement: State Key Structure

All navigation state SHALL be stored under a namespaced key structure in `sessionStorage`:

| Key | Value | Format |
|-----|-------|--------|
| `animewing-nav-scroll` | Scroll position JSON | `{ top: number, left: number, path: string }` |
| `animewing-fav-tab` | Active tab key | `"ultimos"` \| `"en_emision"` \| `"concluido"` |

#### Scenario: Keys are namespaced

- GIVEN the app stores navigation state
- WHEN inspecting sessionStorage
- THEN all keys are prefixed with `animewing-`
- AND no keys collide with other apps sharing the origin

#### Scenario: State is cleared on session end

- GIVEN the user closes the browser tab
- WHEN a new session starts
- THEN sessionStorage is empty and no stale state persists
