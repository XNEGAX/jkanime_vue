@echo off
chcp 65001 >nul 2>&1
title Build APK - AnimeWing

setlocal EnableDelayedExpansion

set "PROJECT_DIR=%~dp0"
set "FRONTEND_DIR=%PROJECT_DIR%frontend"
set "ANDROID_DIR=%FRONTEND_DIR%\android"
set "JAVA21_HOME=C:\Program Files\Microsoft\jdk-21.0.11.10-hotspot"
set "ANDROID_SDK=%LOCALAPPDATA%\Android\Sdk"

echo ============================================
echo   Build APK - AnimeWing
echo ============================================
echo.

echo [1/3] Building Vue frontend...
cd /d "%FRONTEND_DIR%"
call npm run build
if %errorlevel% neq 0 (
    echo ERROR: Frontend build failed.
    pause
    exit /b 1
)
echo   Frontend built.
echo.

echo [2/3] Syncing Capacitor...
call npx cap sync android
if %errorlevel% neq 0 (
    echo ERROR: Capacitor sync failed.
    pause
    exit /b 1
)
echo   Capacitor synced.
echo.

echo [3/3] Building APK (debug)...
set "JAVA_HOME=%JAVA21_HOME%"
set "ANDROID_HOME=%ANDROID_SDK%"
set "ANDROID_SDK_ROOT=%ANDROID_SDK%"
cd /d "%ANDROID_DIR%"
call gradlew assembleDebug --no-daemon
if %errorlevel% neq 0 (
    echo ERROR: APK build failed.
    pause
    exit /b 1
)
echo.
echo ============================================
echo   APK built successfully!
echo   Location: android\app\build\outputs\apk\debug\app-debug.apk
echo ============================================
pause
