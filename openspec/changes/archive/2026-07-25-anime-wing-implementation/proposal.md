# Proposal: AnimeWing Rebrand + Feature Improvements

## Intent

Rebrand jkanime_vue to AnimeWing with a Wing Zero Custom design system (CSS variables + light palette), extract reusable components, fix navigation state preservation, improve tab behaviors (click→play, download overlay, grouping), and configure Android/branding. The existing dark theme (#0f0f0f/#e94560) is replaced entirely by the light Wing Zero palette.

## Scope

### In Scope

- CSS variables: introduce `:root` Wing Zero palette, replace ALL hardcoded hex in every .vue + style.css
- Component extraction: TrendingCard.vue + TrendingGrid.vue from inline scoped styles in FavoritesView.vue
- Backend: verify/enrich `/api/ultimos-episodios/` (already partially done — confirm + complete if gaps)
- Tab Últimos episodios: fix click→play (reuse ChaptersView play flow), confirm download overlay reuse
- Tab En emisión: trending-card, chronological grouping from today backwards
- Tab Concluidos: trending-grid, alphabetical grouping
- Navigation state: preserve scroll position, selected tab, expanded group across back-navigation
- Rebranding: all name references (package.json, index.html, capacitor.config, build.gradle, strings.xml, navbar, config screen, run scripts, admin verbose_name)
- Android: Capacitor (decision below), custom launcher icons, splash screen, rebrand strings
- Logo/favicon: integrate PI_Wing_Zero_Mercy.webp into index.html + Android splash

### Out of Scope

- PWA manifest (future work)
- Native Kotlin rewrite
- Testing infrastructure (none exists, not in scope)
- PlayerView.vue cleanup (dead code, cosmetic only)
- New features beyond spec improvements

## Capabilities

### New Capabilities

- `wing-zero-design-system`: CSS variables + Wing Zero palette applied project-wide
- `trending-components`: Extracted TrendingCard.vue and TrendingGrid.vue
- `navigation-state`: Scroll/tab/group preservation on back-navigation
- `anime-wing-branding`: Full rebrand across web, Android, scripts, admin

### Modified Capabilities

None — no existing specs in `openspec/specs/`.

## Approach

1. **Phase 1 — Design System**: Define `:root` variables in style.css, replace hardcoded hex across all components. Single commit, full visual regression.
2. **Phase 2 — Component Extraction**: Extract TrendingCard/TrendingGrid from FavoritesView inline styles. Refactor all three tabs.
3. **Phase 3 — Tab Behaviors**: Fix Últimos episodios click→play (reuse ChaptersView logic), verify download overlay, implement Concluidos alphabetical grouping.
4. **Phase 4 — Navigation State**: Implement scroll/tab/group preservation using sessionStorage + router scrollBehavior.
5. **Phase 5 — Branding + Android**: Rename all references, generate custom icons, update splash, update Capacitor config.
6. **Phase 6 — Backend Verification**: Audit `/api/ultimos-episodios/` enrichment completeness.

## Android Architecture Decision: Capacitor (Recommended)

| Criterion | Capacitor | Native Kotlin |
|-----------|-----------|---------------|
| Code reuse | 100% Vue code shared | Full rewrite |
| Maintenance | Single codebase | Two codebases diverge |
| UX parity | Identical (web rendering) | Custom needed |
| Effort | Low (config + icons) | High (months) |
| Performance | Adequate for content app | Better, but unnecessary |

**Justification**: This is a content-consumption app with scraping + download + playback. Capacitor already works (ConfigScreen, API layer, build pipeline). Native Kotlin adds months of work for marginal UX gains. Keep Capacitor, invest in branding and features instead.

## Affected Areas

| Area | Impact | Files |
|------|--------|-------|
| Design system | Modified | `style.css`, ALL `.vue` components |
| Component extraction | New + Modified | `FavoritesView.vue`, new `TrendingCard.vue`, `TrendingGrid.vue` |
| Tab behaviors | Modified | `FavoritesView.vue` |
| Navigation | Modified | `FavoritesView.vue`, `router/index.js` |
| Branding | Modified | `package.json`, `index.html`, `capacitor.config.json`, `build.gradle`, `strings.xml`, `AppNavbar.vue`, `ConfigScreen.vue`, `run.bat`, `run.py`, `build-apk.bat`, `apps.py` |
| Android icons | Modified | `android/app/src/main/res/mipmap-*/` |
| Backend | Verified | `series/views.py` (`api_ultimos_episodios`) |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Dark→light migration breaks readability | Medium | Audit contrast ratios; test all states before/after |
| Capacitor app identity change (`applicationId`) | High | Changing `com.jkanime.gestor` forces reinstall; keep ID, only change display name |
| CSS variable refactor touches every file | High | Do in single atomic phase, verify build succeeds |
| No test suite | High | Manual smoke test after each phase |

## Rollback Plan

Each phase is independently revertible via git. CSS variable migration: revert style.css + all .vue changes. Branding: revert name strings. Android: revert `capacitor.config.json` + `strings.xml`. All changes are additive/refactor — no destructive data migrations.

## Dependencies

- Existing backend enrichment logic (partially implemented) — verify in Phase 6
- `PI_Wing_Zero_Mercy.webp` already exists in `backend/media/`

## Success Criteria

- [ ] All hardcoded hex replaced with CSS variable references
- [ ] TrendingCard/TrendingGrid extracted and reusable
- [ ] Click on trending episode triggers play flow (not external URL)
- [ ] Back-navigation preserves scroll, tab, group, section
- [ ] All "jkanime" references renamed to "anime-wing" / "AnimeWing"
- [ ] Android app uses custom branded icons and splash
- [ ] `npm run build` succeeds with zero errors

## Proposal Question Round — Resolved

1. **Android applicationId**: Change to `com.animewing.app` (clean rebrand, accepts forced reinstall for existing users).
2. **PWA manifest**: Include basic manifest.json in Phase 5.
3. **PlayerView.vue**: Delete dead code now (route redirects to /).
4. **Search in Concluidos**: Include search filtering like En emisión.

## Scope Adjustments (from user decisions)

- **Phase 5** now includes: PWA manifest.json + PlayerView.vue deletion + applicationId change to `com.animewing.app`
- **Phase 3** now includes: search filtering in Concluidos tab
