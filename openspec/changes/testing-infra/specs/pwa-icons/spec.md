# PWA Icons Specification

## Purpose

Generate PWA-ready PNG icons at 192x192 and 512x512 from the existing project logo, place them in the frontend public directory, and register them in `manifest.json` for PWA install prompts and browser tab icons.

## Requirements

### Requirement: Icon Generation

The project SHALL generate two PNG files — `icon-192.png` (192x192) and `icon-512.png` (512x512) — from the source image at `backend/media/PI_Wing_Zero_Mercy.webp`.

#### Scenario: Both PNG files exist after generation

- GIVEN the source file `backend/media/PI_Wing_Zero_Mercy.webp` exists
- WHEN the icon generation step runs
- THEN `frontend/public/icon-192.png` exists
- AND `frontend/public/icon-512.png` exists

#### Scenario: Icons have correct dimensions

- GIVEN the generation step completed
- WHEN `icon-192.png` is inspected
- THEN its dimensions are exactly 192x192 pixels
- AND `icon-512.png` dimensions are exactly 512x512 pixels

#### Scenario: Source image missing produces error

- GIVEN `backend/media/PI_Wing_Zero_Mercy.webp` does not exist
- WHEN the icon generation step runs
- THEN the process exits with a non-zero code
- AND a descriptive error message is printed

### Requirement: Manifest Icon References

The project's `manifest.json` (in `frontend/public/`) SHALL reference both generated icons with their correct `sizes` and `purpose` attributes.

#### Scenario: Manifest contains 192x192 entry

- GIVEN `frontend/public/manifest.json` exists
- WHEN the file is parsed as JSON
- THEN `icons` array contains an entry with `"sizes": "192x192"` and `"src": "/icon-192.png"`

#### Scenario: Manifest contains 512x512 entry

- GIVEN `frontend/public/manifest.json` exists
- WHEN the file is parsed as JSON
- THEN `icons` array contains an entry with `"sizes": "512x512"` and `"src": "/icon-512.png"`

#### Scenario: Icon purpose includes maskable

- GIVEN both icon entries are present in `manifest.json`
- WHEN either entry is inspected
- THEN the `purpose` field includes `"maskable"` or `"any"`

### Requirement: Build Compatibility

Generated icon files MUST NOT interfere with the existing Vite build (`npm run build`). Icons placed in `frontend/public/` are copied verbatim to `dist/` by Vite.

#### Scenario: Build completes with icons in place

- GIVEN `icon-192.png` and `icon-512.png` exist in `frontend/public/`
- WHEN `npm run build` is executed from `frontend/`
- THEN the build exits with code 0
- AND `dist/icon-192.png` and `dist/icon-512.png` exist in the output

#### Scenario: Build completes without icons (optional files)

- GIVEN no icon PNGs exist in `frontend/public/`
- WHEN `npm run build` is executed from `frontend/`
- THEN the build exits with code 0
- AND no icon files appear in `dist/`
