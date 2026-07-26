# Wing Zero Design System Specification

## Purpose

Define the Wing Zero Custom CSS variable system and mandate its use across all frontend styles, replacing all hardcoded hex color values with semantic tokens.

## Requirements

### Requirement: Root CSS Variables

The system SHALL define a `:root` CSS custom property block in `frontend/src/style.css` with the Wing Zero palette tokens:

| Token | Value | Role |
|-------|-------|------|
| `--bg-primary` | `#F7F8FC` | Page background |
| `--primary` | `#00539C` | Primary brand color |
| `--text-main` | `#3A3D42` | Body text |
| `--bg-secondary` | `#D18854` | Secondary surfaces |
| `--accent-cta` | `#F4C430` | Call-to-action highlights |
| `--accent-subtle` | `#C8BFE7` | Subtle decorative accents |
| `--text-muted` | `#6C757D` | De-emphasized text |
| `--border-light` | `#E2E8F0` | Light borders |

#### Scenario: Variables exist at load time

- GIVEN the app loads in any browser
- WHEN CSS is parsed
- THEN all `--bg-primary`, `--primary`, `--text-main`, and related tokens are resolvable
- AND no `var(--undefined)` fallback occurs due to missing definitions

#### Scenario: Dark theme is fully replaced

- GIVEN the migration is complete
- WHEN any element renders
- THEN no hardcoded `#0f0f0f`, `#e94560`, `#1a1a2e`, or `#16213e` values remain in CSS

### Requirement: Hardcoded Hex Migration

Every `.vue` component and `style.css` SHALL replace all hardcoded hex color values with `var(--token)` references. The mapping is:

| Old Value | New Variable |
|-----------|-------------|
| `#0f0f0f`, `#1a1a1a` | `var(--bg-primary)` |
| `#e94560` | `var(--primary)` |
| `#e0e0e0` | `var(--text-main)` |
| `#1a1a2e` | `var(--bg-secondary)` / `var(--primary)` context |
| `#333`, `#444` | `var(--border-light)` / `var(--bg-secondary)` |
| `#888`, `#666` | `var(--text-muted)` |
| `#27ae60` | Kept as-is (semantic success, not in palette) |

#### Scenario: Full component audit

- GIVEN all `.vue` files under `frontend/src/`
- WHEN a grep for `#[0-9a-fA-F]{3,8}` runs against scoped `<style>` blocks
- THEN zero matches contain colors that should map to palette tokens
- AND zero matches remain for `#e94560` or `#0f0f0f`

#### Scenario: style.css is fully migrated

- GIVEN `frontend/src/style.css`
- WHEN all `.btn-primary`, `.btn-secondary`, `th`, `tr:hover`, `.spinner`, `.progress-fill` rules are inspected
- THEN every color uses `var(--token)` instead of hardcoded hex

### Requirement: Light Palette Contrast

The system SHALL ensure all text-background combinations meet WCAG AA contrast (4.5:1 minimum):

- `--text-main` (#3A3D42) on `--bg-primary` (#F7F8FC) >= 4.5:1
- `--primary` (#00539C) on `--bg-primary` (#F7F8FC) >= 4.5:1
- `--text-muted` (#6C757D) on `--bg-primary` (#F7F8FC) >= 3:1 (large text only)

#### Scenario: Readability on light background

- GIVEN the page renders with `--bg-primary` as background
- WHEN body text displays at 14px
- THEN contrast ratio between `--text-main` and `--bg-primary` is at least 4.5:1

#### Scenario: Primary accent on light background

- GIVEN a button with `--primary` background
- WHEN rendered at normal size
- THEN `#fff` text on `--primary` achieves at least 4.5:1 contrast

### Requirement: Files Affected

The migration SHALL touch every file listed below:

- `frontend/src/style.css`
- `frontend/src/views/SeriesView.vue`
- `frontend/src/views/ChaptersView.vue`
- `frontend/src/views/FavoritesView.vue`
- `frontend/src/components/AppSidebar.vue`
- `frontend/src/components/AppNavbar.vue`
- `frontend/src/components/ConfigScreen.vue`
- `frontend/src/components/DownloadDrawer.vue`
- `frontend/src/components/DownloadItem.vue`
- `frontend/src/components/VideoPlayerModal.vue`

#### Scenario: No file left behind

- GIVEN the migration is complete
- WHEN `grep -r "#e94560" frontend/src/` runs
- THEN zero results return
- AND `grep -r "#0f0f0f" frontend/src/` returns zero results
