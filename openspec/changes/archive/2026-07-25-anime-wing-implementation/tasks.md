# Tasks: AnimeWing Rebrand + Feature Improvements

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 650–750 (additions + deletions) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 → PR 2 → PR 3 → PR 4 |
| Delivery strategy | ask-on-risk |
| Chain strategy | stacked-to-main |

Decision needed before apply: No (resolved: stacked-to-main)
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | CSS variable design system | PR 1 | `cd frontend && npm run build` | Browser: every view renders with light palette | Revert style.css + all .vue style changes |
| 2 | Component extraction + tab behaviors | PR 2 | `cd frontend && npm run build` | FavoritesView: all 3 tabs render cards, click→play works | Revert TrendingCard/Grid + FavoritesView changes |
| 3 | Navigation state preservation | PR 3 | `cd frontend && npm run build` | Navigate to deep position → series detail → back → scroll + tab restored | Revert sessionStorage + scrollBehavior changes |
| 4 | Branding + Android + cleanup | PR 4 | `grep -ri "jkanime" frontend/src/ run.bat run.py build-apk.bat backend/series/apps.py` | Tab title shows AnimeWing, APK builds with new identity | Revert name strings + config + PlayerView deletion |

## Phase 1: Wing Zero Design System

- [x] 1.1 Add `:root` CSS custom property block to `frontend/src/style.css` with all 8 Wing Zero palette tokens (bg-primary, primary, text-main, bg-secondary, accent-cta, accent-subtle, text-muted, border-light)
- [x] 1.2 Replace all hardcoded hex in `frontend/src/style.css` (.btn-primary, .btn-secondary, th, tr:hover, .spinner, .progress-fill) with `var(--token)` references
- [x] 1.3 Replace hardcoded hex in `frontend/src/views/SeriesView.vue` scoped styles with CSS variables
- [x] 1.4 Replace hardcoded hex in `frontend/src/views/ChaptersView.vue` scoped styles with CSS variables
- [x] 1.5 Replace hardcoded hex in `frontend/src/views/FavoritesView.vue` scoped styles with CSS variables
- [x] 1.6 Replace hardcoded hex in `frontend/src/components/AppSidebar.vue` scoped styles with CSS variables
- [x] 1.7 Replace hardcoded hex in `frontend/src/components/AppNavbar.vue` scoped styles with CSS variables
- [x] 1.8 Replace hardcoded hex in `frontend/src/components/ConfigScreen.vue` scoped styles with CSS variables
- [x] 1.9 Replace hardcoded hex in `frontend/src/components/DownloadDrawer.vue` scoped styles with CSS variables
- [x] 1.10 Replace hardcoded hex in `frontend/src/components/DownloadItem.vue` scoped styles with CSS variables
- [x] 1.11 Replace hardcoded hex in `frontend/src/components/VideoPlayerModal.vue` scoped styles with CSS variables
- [x] 1.12 Verify: `grep -r "#e94560\|#0f0f0f\|#1a1a2e" frontend/src/` returns zero results (only PlayerView.vue dead code remains, scheduled for Phase 5 deletion)
- [x] 1.13 Verify: `cd frontend && npm run build` succeeds with zero errors

## Phase 2: Component Extraction

- [x] 2.1 Create `frontend/src/components/TrendingCard.vue` with props (image, title, subtitle, showFav, isFavorite, downloadState), events (click, toggle-fav), and overlay slot
- [x] 2.2 Create `frontend/src/components/TrendingGrid.vue` with props (minCardWidth, gap) and default slot, using CSS grid with `auto-fill` + `minmax`
- [x] 2.3 Refactor FavoritesView Últimos episodios tab to use `<TrendingGrid>` + `<TrendingCard>` with download overlay slot
- [x] 2.4 Refactor FavoritesView En emisión tab to use `<TrendingGrid>` + `<TrendingCard>` with showFav/isFavorite
- [x] 2.5 Refactor FavoritesView Concluidos tab to use `<TrendingGrid>` + `<TrendingCard>` with showFav/isFavorite and download counts
- [x] 2.6 Remove ~200 lines of inline trending-card/trending-grid scoped styles from FavoritesView.vue
- [x] 2.7 Verify: `cd frontend && npm run build` succeeds with zero errors

## Phase 3: Tab Behaviors

- [x] 3.1 Verify existing `handleEpisodio()` flow (lines 355-395) handles all 4 scenarios: capitulo_id+valid, capitulo_id+invalid, no capitulo_id+serie_id, no capitulo_id+no serie_id
- [x] 3.2 Verify download overlay renders correctly in TrendingCard via overlay slot for Últimos episodios tab
- [x] 3.3 Verify search filtering works in En emisión tab (`emisionFiltradas` computed)
- [x] 3.4 Verify search filtering works in Concluidos tab (`concluidasFiltradas` computed)
- [x] 3.5 Verify chronological grouping in En emisión (from today backwards, empty days hidden)
- [x] 3.6 Verify alphabetical grouping in Concluidos (by first letter of nombre)
- [x] 3.7 Document any gaps found; no new logic expected (existing code already implements spec)

## Phase 4: Navigation State

- [x] 4.1 Add `onBeforeRouteLeave` in FavoritesView.vue to save activeTab and scroll position to sessionStorage keys `animewing-fav-tab` and `animewing-nav-scroll`
- [x] 4.2 Restore activeTab from sessionStorage in FavoritesView `onMounted` with fallback to `"ultimos"` for invalid values
- [x] 4.3 Restore scroll position via `nextTick` after tab data loads
- [x] 4.4 Add `scrollBehavior` function to `frontend/src/router/index.js` that reads `animewing-nav-scroll` from sessionStorage for `/favoritos` route
- [x] 4.5 Verify: navigate to deep scroll position → series detail → back → scroll and tab restored (±20px tolerance)
- [x] 4.6 Verify: new session starts at top with no sessionStorage state

## Phase 5: Branding + Android

- [x] 5.1 Rename `frontend/package.json` name from `jkanime-vue` to `anime-wing`
- [x] 5.2 Update `frontend/index.html`: title → AnimeWing, add favicon link to PI_Wing_Zero_Mercy.webp, add viewport meta for Android, add manifest link
- [x] 5.3 Create `frontend/public/manifest.json` with AnimeWing name, Wing Zero theme colors, and icon references
- [x] 5.4 Update `frontend/capacitor.config.json`: appId → `com.animewing.app`, appName → AnimeWing, splash config
- [x] 5.5 Update `frontend/android/app/build.gradle`: applicationId + namespace → `com.animewing.app`
- [x] 5.6 Update `frontend/android/app/src/main/res/values/strings.xml`: all 4 strings to AnimeWing / com.animewing.app
- [x] 5.7 Generate branded launcher icons from `backend/media/PI_Wing_Zero_Mercy.webp` for all 5 mipmap densities (48–192px)
- [x] 5.8 Update AppNavbar.vue brand text → "AnimeWing"
- [x] 5.9 Update ConfigScreen.vue title → "AnimeWing"
- [x] 5.10 Delete `frontend/src/views/PlayerView.vue` (dead code)
- [x] 5.11 Remove `/reproducir/:id` redirect from `frontend/src/router/index.js`
- [x] 5.12 Update `run.bat` console title + echo → AnimeWing
- [x] 5.13 Update `run.py` print message → AnimeWing
- [x] 5.14 Update `build-apk.bat` console title → AnimeWing
- [x] 5.15 Update `backend/series/apps.py` verbose_name → AnimeWing
- [x] 5.16 Verify: `grep -ri "jkanime" frontend/src/ run.bat run.py build-apk.bat backend/series/apps.py` returns zero brand-name results (scraper URLs exempt)
- [x] 5.17 Move `MainActivity.java` from `com/jkanime/gestor/` to `com/animewing/app/` and update package declaration

## Phase 6: Backend Verification

- [x] 6.1 Audit `backend/series/views.py` lines 635-734: confirm series auto-creation, capitulo auto-creation, image replacement, all 3 enrichment fields present
- [x] 6.2 Verify response format matches spec: every episode has `serie_id`, `capitulo_id`, `archivo_existe`
- [x] 6.3 Document any gaps found; no code changes expected
