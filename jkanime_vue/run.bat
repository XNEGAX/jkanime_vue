@echo off
setlocal enabledelayedexpansion
title JKanime Gestor
cd /d "%~dp0"

set "PYTHON=C:\Users\xnega\AppData\Local\Python\pythoncore-3.14-64\python.exe"
set "REDIS_PORT=6379"

echo ========================================
echo    JKanime Gestor - Iniciando...
echo ========================================
echo.

REM ---- Verificar entorno Python ----
echo [CHECK] Verificando Python...
%PYTHON% --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python no encontrado en: %PYTHON%
    pause
    exit /b 1
)
%PYTHON% -c "import django" >nul 2>&1
if %errorlevel% neq 1 (
    echo [SETUP] Instalando dependencias...
    %PYTHON% -m pip install -r "%~dp0..\requirements.txt"
    if %errorlevel% neq 0 (
        echo [ERROR] Fallo al instalar dependencias.
        pause
        exit /b 1
    )
    echo.
)

cls

REM ---- Buscar redis-server ----
echo [CHECK] Buscando Redis...
set "REDIS_CMD="
where redis-server >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=*" %%i in ('where redis-server') do (
        if not defined REDIS_CMD set "REDIS_CMD=%%i"
    )
    echo [REDIS] Encontrado en PATH: %REDIS_CMD%
    goto :redis_ok
)

cls

REM Buscar en WinGet Packages
for /d %%D in ("%LOCALAPPDATA%\Microsoft\WinGet\Packages\taizod1024.redis-windows-fork_*") do (
    if exist "%%D\Redis-8.8.0-Windows-x64-msys2\redis-server.exe" (
        set "REDIS_CMD=%%D\Redis-8.8.0-Windows-x64-msys2\redis-server.exe"
        echo [REDIS] Encontrado en WinGet.
        goto :redis_ok
    )
)

cls

REM Buscar en Program Files
if exist "C:\Program Files\Redis\redis-server.exe" (
    set "REDIS_CMD=C:\Program Files\Redis\redis-server.exe"
    echo [REDIS] Encontrado en Program Files.
    goto :redis_ok
)

cls

REM No encontrado - instalar
echo [REDIS] No encontrado. Instalando...
winget install taizod1024.redis-windows-fork --accept-package-agreements --accept-source-agreements
if %errorlevel% neq 0 (
    echo [ERROR] Fallo la instalacion de Redis.
    echo         Instalalo manualmente: winget install taizod1024.redis-windows-fork
    pause
    exit /b 1
)

cls

REM Buscar de nuevo
for /d %%D in ("%LOCALAPPDATA%\Microsoft\WinGet\Packages\taizod1024.redis-windows-fork_*") do (
    if exist "%%D\Redis-8.8.0-Windows-x64-msys2\redis-server.exe" (
        set "REDIS_CMD=%%D\Redis-8.8.0-Windows-x64-msys2\redis-server.exe"
        goto :redis_ok
    )
)

cls

echo [ERROR] Redis no encontrado despues de instalar.
pause
exit /b 1

:redis_ok
echo [REDIS] Usando: %REDIS_CMD%

REM Buscar redis-cli en la misma carpeta que redis-server
set "REDIS_CLI="
for %%F in ("%REDIS_CMD%") do set "REDIS_DIR=%%~dpF"
if exist "%REDIS_DIR%redis-cli.exe" (
    set "REDIS_CLI=%REDIS_DIR%redis-cli.exe"
) else (
    REM Buscar en PATH
    where redis-cli >nul 2>&1
    if %errorlevel% equ 0 (
        for /f "tokens=*" %%i in ('where redis-cli') do (
            if not defined REDIS_CLI set "REDIS_CLI=%%i"
        )
    )
)
if not defined REDIS_CLI (
    echo [WARN] redis-cli.exe no encontrado, usando redis-server para ping
    set "REDIS_CLI=%REDIS_CMD%"
)

REM ---- Verificar si Redis ya esta corriendo ----
"%REDIS_CLI%" -p %REDIS_PORT% ping >nul 2>&1
if %errorlevel% equ 0 (
    echo [REDIS] Ya esta corriendo en puerto %REDIS_PORT%.
    goto :redis_running
)

echo [REDIS] Iniciando servidor Redis...
start "Redis" /B "%REDIS_CMD%" --port %REDIS_PORT% --loglevel warning
timeout /t 4 >nul
"%REDIS_CLI%" -p %REDIS_PORT% ping >nul 2>&1
if %errorlevel% equ 0 (
    echo [REDIS] Servidor iniciado correctamente.
) else (
    echo [ERROR] No se pudo iniciar Redis.
    pause
    exit /b 1
)


cls

:redis_running
echo.

REM ---- Ejecutar migraciones ----
echo [DB] Ejecutando migraciones...
%PYTHON% manage.py migrate --run-syncdb
echo.

REM ---- Crear carpeta de descargas ----
if not exist "descargas" (
    mkdir descargas
    echo [DIR] Carpeta descargas/ creada.
)

cls

REM ---- Verificar e iniciar/reiniciar Celery Workers ----
echo [CELERY] Verificando Celery workers...

REM Worker de actualizaciones
tasklist /FI "WINDOWTITLE eq Celery Actualizaciones" 2>nul | find /i "celery" >nul 2>&1
if %errorlevel% equ 0 (
    echo [CELERY] Worker actualizaciones activo, reiniciando...
    taskkill /FI "WINDOWTITLE eq Celery Actualizaciones" /F >nul 2>&1
    timeout /t 2 >nul
)
echo [CELERY] Iniciando worker actualizaciones...
start "Celery Actualizaciones" /B "%PYTHON%" -m celery -A jkanime_vue worker --loglevel=info --pool=solo --queues=actualizaciones --concurrency=1
timeout /t 3 >nul

REM Worker de descargas
tasklist /FI "WINDOWTITLE eq Celery Descargas" 2>nul | find /i "celery" >nul 2>&1
if %errorlevel% equ 0 (
    echo [CELERY] Worker descargas activo, reiniciando...
    taskkill /FI "WINDOWTITLE eq Celery Descargas" /F >nul 2>&1
    timeout /t 2 >nul
)
echo [CELERY] Iniciando worker descargas (3 en paralelo)...
start "Celery Descargas" /B "%PYTHON%" -m celery -A jkanime_vue worker --loglevel=info --pool=gevent --queues=descargas --concurrency=3
timeout /t 5 >nul
echo [CELERY] Workers en background.
echo.

REM ---- Abrir navegador ----
start "" cmd /c "timeout /t 2 >nul && start http://127.0.0.1:8000"

REM ---- Iniciar servidor Django ----
echo ========================================
echo [DJANGO] http://127.0.0.1:8000
echo          Presiona Ctrl+C para detener.
echo ========================================
echo.
%PYTHON% manage.py runserver 0.0.0.0:8000

pause
