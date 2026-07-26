# Design: AnimeWing Rebrand + Feature Improvements

## Technical Approach

Six sequential phases: (1) CSS variable foundation, (2) component extraction, (3) tab behavior fixes, (4) navigation state, (5) branding + Android, (6) backend verification. Each phase is independently revertible via git. The frontend is a Vue 3 SPA served by Django; Android wraps it via Capacitor.

## Architecture Decisions

| Decision | Choice | Alternatives | Rationale |
|----------|--------|--------------|-----------|
| CSS variable location | `:root` in `style.css` | Per-component `defineProps`, Tailwind | Global `:root` is simplest; all 10 files already import style.css. Tailwind adds a build dependency for no gain in a 10-file project. |
| Dark→light migration | Single atomic phase | Incremental per-file | Incremental leaves broken contrast mid-migration. One commit = one visual state. Revert is clean. |
| Component extraction | Separate `.vue` files in `components/` | Inline render functions, slots-only wrappers | `.vue` SFC is the established pattern. Keeps scoped styles colocated. |
| Navigation state | sessionStorage + router `scrollBehavior` | localStorage, Pinia, vuex-persist | sessionStorage auto-clears on tab close. localStorage persists too long. Pinia doesn't survive navigation to non-Pinia routes. |
| Android applicationId | Change to `com.animewing.app` | Keep `com.jkanime.gestor`, only change display name | User explicitly chose clean rebrand (accepts reinstall). |
| Icon generation | CLI resize from `PI_Wing_Zero_Mercy.webp` | Manual, Capacitor community plugin | CLI (ImageMagick/similar) is deterministic, scriptable, repeatable. |
| PlayerView cleanup | Delete file + remove route | Leave as dead code | Spec requires removal. Reduces confusion. Route redirect already exists. |

## Data Flow

### Click→Play (Últimos episodios tab)

```
User clicks TrendingCard
  │
  ├─ ep.capitulo_id === null
  │   ├─ ep.serie_id exists → router.push(/serie/{id})
  │   └─ no serie_id → window.open(ep.url)
  │
  └─ ep.capitulo_id exists
      │
      ├─ verificarCapitulo(id) → { valido: true }
      │   └─ playerCapituloId = id → VideoPlayerModal opens
      │
      └─ verificarCapitulo(id) → { valido: false }
          └─ descargarCapitulo(id) → dlStore.addDownload()
              └─ onComplete callback → playerCapituloId = id
```

This reuses the existing `handleEpisodio()` + `iniciarDescargaTrending()` in FavoritesView (lines 355-395), which already implements this exact flow. Phase 3 verifies and documents it; no new logic needed.

### Navigation State Preservation

```
FavoritesView onLeave
  │
  ├─ Save activeTab → sessionStorage("animewing-fav-tab")
  ├─ Save scroll position → sessionStorage("animewing-nav-scroll")
  │   └─ { top, left, path: "/favoritos" }
  │
FavoritesView onMounted
  │
  ├─ Read sessionStorage("animewing-fav-tab") → set activeTab (fallback: "ultimos")
  ├─ Load tab data via loadTabData(activeTab)
  └─ nextTick → scrollBehavior reads sessionStorage("animewing-nav-scroll")
      └─ router resolves { top: saved.top, left: saved.left }
```

## File Changes

### Phase 1 — Wing Zero Design System

| File | Action | Description |
|------|--------|-------------|
| `frontend/src/style.css` | Modify | Add `:root` block with 8 CSS tokens. Replace all hardcoded hex with `var(--token)`. |
| `frontend/src/views/SeriesView.vue` | Modify | Replace scoped hex colors with CSS variables |
| `frontend/src/views/ChaptersView.vue` | Modify | Replace scoped hex colors with CSS variables |
| `frontend/src/views/FavoritesView.vue` | Modify | Replace scoped hex colors with CSS variables |
| `frontend/src/components/AppSidebar.vue` | Modify | Replace scoped hex colors with CSS variables |
| `frontend/src/components/AppNavbar.vue` | Modify | Replace scoped hex colors with CSS variables |
| `frontend/src/components/ConfigScreen.vue` | Modify | Replace scoped hex colors with CSS variables |
| `frontend/src/components/DownloadDrawer.vue` | Modify | Replace scoped hex colors with CSS variables |
| `frontend/src/components/DownloadItem.vue` | Modify | Replace scoped hex colors with CSS variables |
| `frontend/src/components/VideoPlayerModal.vue` | Modify | Replace scoped hex colors with CSS variables |

### Phase 2 — Component Extraction

| File | Action | Description |
|------|--------|-------------|
| `frontend/src/components/TrendingCard.vue` | Create | Extract card component with props: image, title, subtitle, showFav, isFavorite, downloadState. Events: click, toggle-fav. Slot: overlay. |
| `frontend/src/components/TrendingGrid.vue` | Create | Grid layout wrapper with `minCardWidth` and `gap` props, default slot. |
| `frontend/src/views/FavoritesView.vue` | Modify | Replace inline trending-card/trending-grid markup with `<TrendingGrid>` + `<TrendingCard>`. Remove ~200 lines of scoped card/grid styles. |

### Phase 3 — Tab Behaviors

| File | Action | Description |
|------|--------|-------------|
| `frontend/src/views/FavoritesView.vue` | Modify | Verify existing `handleEpisodio()` flow. Add search filtering to Concluidos tab (already present in computed `concluidasFiltradas`). Verify download overlay integration with extracted TrendingCard slot. |

### Phase 4 — Navigation State

| File | Action | Description |
|------|--------|-------------|
| `frontend/src/views/FavoritesView.vue` | Modify | Add `onBeforeRouteLeave` to save activeTab + scroll position to sessionStorage. Restore on mount. |
| `frontend/src/router/index.js` | Modify | Add `scrollBehavior` function that reads `animewing-nav-scroll` from sessionStorage for `/favoritos`. |

### Phase 5 — Branding + Android

| File | Action | Description |
|------|--------|-------------|
| `frontend/package.json` | Modify | `"name": "anime-wing"` |
| `frontend/index.html` | Modify | `<title>AnimeWing</title>`, add `<link rel="icon">` + `<link rel="manifest">`, add viewport meta for Android |
| `frontend/public/manifest.json` | Create | PWA manifest: name, theme_color, icons |
| `frontend/capacitor.config.json` | Modify | `appId: "com.animewing.app"`, `appName: "AnimeWing"`, splash config |
| `frontend/android/app/build.gradle` | Modify | `applicationId "com.animewing.app"`, `namespace "com.animewing.app"` |
| `frontend/android/app/src/main/res/values/strings.xml` | Modify | All 4 strings → AnimeWing / com.animewing.app |
| `frontend/android/app/src/main/res/mipmap-*/` | Modify | Replace default icons with generated branded icons (5 densities) |
| `frontend/src/components/AppNavbar.vue` | Modify | Brand text → "AnimeWing" |
| `frontend/src/components/ConfigScreen.vue` | Modify | Title → "AnimeWing" |
| `frontend/src/views/PlayerView.vue` | Delete | Dead code — route already redirects to `/` |
| `frontend/src/router/index.js` | Modify | Remove `/reproducir/:id` redirect |
| `run.bat` | Modify | Console title + echo → AnimeWing |
| `run.py` | Modify | Print message → AnimeWing |
| `build-apk.bat` | Modify | Console title → AnimeWing |
| `backend/series/apps.py` | Modify | `verbose_name = 'AnimeWing'` |

### Phase 6 — Backend Verification

| File | Action | Description |
|------|--------|-------------|
| `backend/series/views.py` | Verify | Confirm enrichment logic (lines 635-734) covers: series auto-creation, capitulo auto-creation, image replacement, all 3 response fields (`serie_id`, `capitulo_id`, `archivo_existe`). Document any gaps. |

### Shared Dependencies

- **Phase 2 depends on Phase 1**: TrendingCard styles must use CSS variables, not hardcoded hex.
- **Phase 3 depends on Phase 2**: Tab behaviors reference extracted TrendingCard/TrendingGrid.
- **Phase 4 depends on Phase 2**: Navigation state restore must work after component extraction.
- **Phase 5 is independent** of Phases 2-4 (branding doesn't touch component logic).
- **Phase 6 is independent** of frontend phases.

## Reuse Strategy

### ChaptersView Play Flow in FavoritesView

FavoritesView already reuses the play flow — `handleEpisodio()` (line 355) and `iniciarDescargaTrending()` (line 383) implement the same verify→play/download→play pattern as ChaptersView's `handleClick()` and `iniciarDescarga()`. The key difference: ChaptersView has full repair/corrupt logic; FavoritesView uses the simpler path (verify + download if invalid). This is correct — trending cards don't need the full repair UX.

### Download Overlay Pattern

The existing `dl-overlay` markup in FavoritesView (lines 51-58) becomes the `overlay` slot of TrendingCard. The parent passes `downloadStatus(ep.capitulo_id)` to TrendingCard's `downloadState` prop; TrendingCard renders the overlay internally. No new pattern needed.

### Existing API Functions

All API functions already exist in `frontend/src/api/index.js`: `getUltimosEpisodios`, `getFavoritosByEstado`, `verificarCapitulo`, `descargarCapitulo`. The download store (`useDownloadStore`) and favorites store (`useFavoritesStore`) are already imported and used. No new API calls required.

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Visual | Dark→light migration renders correctly | Manual smoke test: load every view, verify contrast, check all states (loading, empty, populated) |
| Build | `npm run build` succeeds with zero errors | Automated via `cd frontend && npm run build` |
| Component | TrendingCard renders with all prop combinations | Manual: verify image, title, subtitle, overlay, fav button, placeholder states |
| Navigation | Back-navigation preserves scroll + tab | Manual: navigate to deep position in Concluidos, go to series detail, press back |
| Branding | No "jkanime" references in source (exempt scraper URLs) | `grep -ri "jkanime" frontend/src/ run.bat run.py build-apk.bat backend/series/apps.py` |
| Android | APK builds and installs with new identity | `build-apk.bat` → install on device → verify icon + name |

**Note**: No test suite exists. All verification is manual + build check. This is a project constraint, not a design choice.

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary.

## Migration / Rollout

No data migration required. All changes are frontend CSS/refactor, config updates, and file renames. Each phase is a separate git commit for clean rollback:

1. `git revert` Phase 1 → dark theme returns
2. `git revert` Phase 2 → inline styles return
3. `git revert` Phase 5 → old branding returns

**Android `applicationId` change** (`com.jkanime.gestor` → `com.animewing.app`) creates a NEW app identity. Existing Android users must uninstall and reinstall. This is accepted per user decision.

## Open Questions

- [ ] Icon generation tool: ImageMagick is available on Windows, but need to confirm `PI_Wing_Zero_Mercy.webp` has enough resolution for 192x192 mipmap. May need to upscale or use a padded version.
- [ ] `PROMPT.md` / `PROMPT2.md` duplicate files: Should these be cleaned up as part of Phase 5 branding? Not in current scope but worth noting.
