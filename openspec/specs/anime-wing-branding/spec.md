# AnimeWing Branding Specification

## Purpose

Rebrand all "jkanime" references to "AnimeWing" across web, Android, scripts, and admin. Configure custom launcher icons, splash screen, PWA manifest, and remove dead code.

## Requirements

### Requirement: Name Reference Changes

The system SHALL update every occurrence listed below:

| File | Field | Old Value | New Value |
|------|-------|-----------|-----------|
| `frontend/package.json` | `name` | `jkanime-vue` | `anime-wing` |
| `frontend/index.html` | `<title>` | `JKanime Gestor` | `AnimeWing` |
| `frontend/capacitor.config.json` | `appId` | `com.jkanime.gestor` | `com.animewing.app` |
| `frontend/capacitor.config.json` | `appName` | `jkanime-vue` | `AnimeWing` |
| `frontend/src/components/AppNavbar.vue` | brand text | `JKanime Gestor` | `AnimeWing` |
| `frontend/src/components/ConfigScreen.vue` | title | `JKanime Gestor` | `AnimeWing` |
| `run.bat` | title + echo | `Jkanime Vue - Gestor de Series` | `AnimeWing` |
| `run.py` | print message | `Jkanime Vue - Gestor de Series` | `AnimeWing` |
| `build-apk.bat` | title | `Build APK - Jkanime Vue` | `Build APK - AnimeWing` |
| `backend/series/apps.py` | `verbose_name` | `Series JKanime` | `AnimeWing` |

#### Scenario: No "jkanime" brand references remain in source

- GIVEN the rebranding is complete
- WHEN `grep -ri "jkanime" frontend/src/ run.bat run.py build-apk.bat backend/series/apps.py` runs
- THEN zero results contain the string as a brand name (scraper URLs/sources are exempt)

#### Scenario: Page title displays AnimeWing

- GIVEN the user opens the app in a browser
- WHEN the tab renders
- THEN the browser tab title shows "AnimeWing"

### Requirement: Android Application ID

The system SHALL change the Android `applicationId` to `com.animewing.app` in:

- `frontend/capacitor.config.json`
- `frontend/android/app/build.gradle` (`applicationId` + `namespace`)
- `frontend/android/app/src/main/res/values/strings.xml` (`package_name`, `custom_url_scheme`)

#### Scenario: New app identity is consistent

- GIVEN all Android config files
- WHEN inspected
- THEN `applicationId`, `namespace`, `package_name`, and `custom_url_scheme` all resolve to `com.animewing.app`

### Requirement: Android Display Strings

The system SHALL update `frontend/android/app/src/main/res/values/strings.xml`:

| String | Old | New |
|--------|-----|-----|
| `app_name` | `jkanime-vue` | `AnimeWing` |
| `title_activity_main` | `jkanime-vue` | `AnimeWing` |
| `package_name` | `com.jkanime.gestor` | `com.animewing.app` |
| `custom_url_scheme` | `com.jkanime.gestor` | `com.animewing.app` |

#### Scenario: Android launcher shows AnimeWing name

- GIVEN the APK is installed on an Android device
- WHEN the app icon displays on the home screen
- THEN the label reads "AnimeWing"

### Requirement: Custom Launcher Icons

The system SHALL replace default Capacitor icons with branded AnimeWing icons generated from `backend/media/PI_Wing_Zero_Mercy.webp` across all mipmap densities:

- `mipmap-mdpi` (48x48)
- `mipmap-hdpi` (72x72)
- `mipmap-xhdpi` (96x96)
- `mipmap-xxhdpi` (144x144)
- `mipmap-xxxhdpi` (192x192)

#### Scenario: Icons are custom branded

- GIVEN the built APK
- WHEN launcher icons are extracted from the APK
- THEN icons match the Wing Zero Mercy logo (not default purple Android icons)

### Requirement: Splash Screen

The system SHALL use `PI_Wing_Zero_Mercy.webp` as the Android splash screen background image, configured via `capacitor.config.json` SplashScreen plugin settings.

#### Scenario: Splash shows branded image

- GIVEN the user opens the Android app from cold start
- WHEN the splash screen displays
- THEN the Wing Zero Mercy logo appears centered on screen

### Requirement: PWA Manifest

The system SHALL create `frontend/public/manifest.json` with:

| Field | Value |
|-------|-------|
| `name` | `AnimeWing` |
| `short_name` | `AnimeWing` |
| `start_url` | `/` |
| `display` | `standalone` |
| `theme_color` | `#00539C` |
| `background_color` | `#F7F8FC` |
| `icons` | Array referencing generated icons from PI_Wing_Zero_Mercy.webp |

#### Scenario: manifest.json is valid

- GIVEN the built app at `frontend/dist/`
- WHEN `manifest.json` is served
- THEN it parses as valid JSON
- AND contains `name`, `start_url`, `display`, and `icons` fields

### Requirement: PlayerView.vue Removal

The system SHALL delete `frontend/src/views/PlayerView.vue` and remove its dead redirect route from `frontend/src/router/index.js`.

#### Scenario: PlayerView no longer exists

- GIVEN the rebranding is complete
- WHEN `frontend/src/views/PlayerView.vue` is checked
- THEN the file does not exist

#### Scenario: Redirect route removed

- GIVEN the router configuration
- WHEN `/reproducir/:id` is inspected
- THEN no redirect rule exists for this path
