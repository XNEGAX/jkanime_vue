@echo off
chcp 65001 >nul 2>&1
title Jkanime Vue - Gestor de Series
setlocal EnableDelayedExpansion

set "PROJECT_DIR=%~dp0"
set "DJANGO_DIR=%PROJECT_DIR%jkanime_vue"
set "VENV_DIR=%PROJECT_DIR%venv"
set "NODE_DIR=%PROJECT_DIR%frontend"

echo ============================================
echo   Jkanime Vue - Gestor de Series
echo ============================================
echo.

REM ============================================
REM  [1] Verificando Python
REM ============================================
echo [1/8] Verificando Python...

set "SYS_PYTHON="

REM Try python in PATH
where python >nul 2>&1
if %errorlevel% equ 0 (
    for /f "delims=" %%V in ('python --version 2^>^&1') do set "PYVER=%%V"
    echo   Encontrado en PATH: !PYVER!
    set "SYS_PYTHON=python"
    goto :python_ok
)

REM Try py launcher
where py >nul 2>&1
if %errorlevel% equ 0 (
    for /f "delims=" %%V in ('py -3 --version 2^>^&1') do set "PYVER=%%V"
    echo   Encontrado py launcher: !PYVER!
    set "SYS_PYTHON=py -3"
    goto :python_ok
)

REM Try common install paths
if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" (
    set "SYS_PYTHON=%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
    goto :python_found_path
)
if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" (
    set "SYS_PYTHON=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    goto :python_found_path
)
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "SYS_PYTHON=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    goto :python_found_path
)
if exist "C:\Python314\python.exe" (
    set "SYS_PYTHON=C:\Python314\python.exe"
    goto :python_found_path
)

echo   Python NO encontrado. Instalando via winget...
winget install Python.Python.3.14 --accept-package-agreements --accept-source-agreements
if %errorlevel% neq 0 (
    echo.
    echo   ERROR: No se pudo instalar Python.
    echo   Instale manualmente desde https://www.python.org/downloads/
    pause
    exit /b 1
)
REM Refresh PATH
set "PATH=%LOCALAPPDATA%\Programs\Python\Python314;%LOCALAPPDATA%\Programs\Python\Python314\Scripts;%PATH%"
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo   Python instalado. Reinicie la consola para que se detecte en PATH.
    echo   Despues vuelva a ejecutar run.bat
    pause
    exit /b 0
)
set "SYS_PYTHON=python"
echo   Python instalado correctamente.
goto :python_ok

:python_found_path
echo   Encontrado: !SYS_PYTHON!

:python_ok
echo.

REM ============================================
REM  [2] Creando virtualenv
REM ============================================
echo [2/8] Verificando virtualenv...
if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo   Creando virtualenv...
    %SYS_PYTHON% -m venv "%VENV_DIR%"
    if %errorlevel% neq 0 (
        echo.
        echo   ERROR: No se pudo crear el virtualenv.
        echo   Verifique que Python funcione correctamente: python --version
        pause
        exit /b 1
    )
    echo   Virtualenv creado en: %VENV_DIR%
) else (
    echo   Virtualenv ya existe.
)

REM Switch to venv Python for everything else
set "PYTHON=%VENV_DIR%\Scripts\python.exe"
set "PIP=%VENV_DIR%\Scripts\pip.exe"
echo.

REM ============================================
REM  [3] Instalando dependencias
REM ============================================
echo [3/8] Instalando dependencias...
%PYTHON% --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo   ERROR: Python del virtualenv no funciona. Recree el venv:
    echo   rmdir /s /q "%VENV_DIR%"
    pause
    exit /b 1
)
%PIP% install -q -r "%PROJECT_DIR%requirements.txt"
if %errorlevel% neq 0 (
    echo.
    echo   ERROR: Fall la instalacion de dependencias.
    pause
    exit /b 1
)
echo   Dependencias OK.
echo.

REM ============================================
REM  [4] Verificando/Instalando Redis
REM ============================================
echo [4/8] Verificando Redis...

REM Check if Redis is already running by connecting to port
where redis-cli >nul 2>&1
if %errorlevel% equ 0 (
    redis-cli -h 127.0.0.1 -p 6379 ping >nul 2>&1
    if !errorlevel! equ 0 (
        echo   Redis ya esta corriendo en puerto 6379.
        goto :redis_ok
    )
)

REM Try to find redis-server.exe in WinGet packages
set "REDIS_SERVER="
for /f "delims=" %%F in ('dir /s /b "%LOCALAPPDATA%\Microsoft\WinGet\Packages\*redis-server.exe" 2^>nul') do (
    set "REDIS_SERVER=%%F"
)

REM Try Program Files
if not defined REDIS_SERVER (
    if exist "C:\Program Files\Redis\redis-server.exe" (
        set "REDIS_SERVER=C:\Program Files\Redis\redis-server.exe"
    )
)

REM Install if not found
if not defined REDIS_SERVER (
    echo   Redis no encontrado. Instalando via winget...
    winget install taizod1024.redis-windows-fork --accept-package-agreements --accept-source-agreements
    for /f "delims=" %%F in ('dir /s /b "%LOCALAPPDATA%\Microsoft\WinGet\Packages\*redis-server.exe" 2^>nul') do (
        set "REDIS_SERVER=%%F"
    )
)

if not defined REDIS_SERVER (
    echo.
    echo   ERROR: No se pudo encontrar ni instalar Redis.
    pause
    exit /b 1
)

echo   Redis encontrado.

REM Start Redis
echo   Iniciando Redis...
start "" "!REDIS_SERVER!" --port 6379
timeout /t 3 >nul

REM Verify
redis-cli -h 127.0.0.1 -p 6379 ping >nul 2>&1
if !errorlevel! neq 0 (
    echo.
    echo   ERROR: Redis no responde despues de iniciar.
    pause
    exit /b 1
)

:redis_ok
echo   Redis OK.
echo.

REM ============================================
REM  [5] Verificando/Instalando Node.js
REM ============================================
echo [5/8] Verificando Node.js...

set "NODE_CMD="
where node >nul 2>&1
if %errorlevel% equ 0 (
    set "NODE_CMD=node"
    for /f "delims=" %%V in ('node --version 2^>^&1') do echo   Encontrado: %%V
    goto :node_ok
)

REM Check common paths
if exist "%PROGRAMFILES%\nodejs\node.exe" (
    set "PATH=%PROGRAMFILES%\nodejs;%PATH%"
    set "NODE_CMD=node"
    goto :node_ok
)
if exist "%LOCALAPPDATA%\Programs\nodejs\node.exe" (
    set "PATH=%LOCALAPPDATA%\Programs\nodejs;%PATH%"
    set "NODE_CMD=node"
    goto :node_ok
)

echo   Node.js NO encontrado. Instalando via winget...
winget install OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements
if %errorlevel% neq 0 (
    echo.
    echo   ERROR: No se pudo instalar Node.js.
    pause
    exit /b 1
)
set "PATH=%PROGRAMFILES%\nodejs;%PATH%"
set "NODE_CMD=node"
echo   Node.js instalado correctamente.

:node_ok
echo.

REM ============================================
REM  [6] Creando directorios y migrando DB
REM ============================================
echo [6/8] Preparando base de datos...
if not exist "%DJANGO_DIR%\media" mkdir "%DJANGO_DIR%\media"
if not exist "%DJANGO_DIR%\descargas" mkdir "%DJANGO_DIR%\descargas"
if not exist "%DJANGO_DIR%\static" mkdir "%DJANGO_DIR%\static"

cd "%DJANGO_DIR%"
"%PYTHON%" manage.py migrate --run-syncdb >nul 2>&1
if %errorlevel% neq 0 (
    echo   ADVERTENCIA: Las migraciones tuvieron problemas, pero se continua...
)
echo   Base de datos OK.
echo.

REM ============================================
REM  [7] Construyendo frontend
REM ============================================
echo [7/8] Verificando frontend...

REM Always rebuild to ensure latest code
if exist "%NODE_DIR%\package.json" (
    echo   Instalando dependencias npm...
    cd "%NODE_DIR%"
    call npm install --silent 2>nul
    echo   Construyendo frontend...
    call npm run build --silent 2>nul
    if %errorlevel% neq 0 (
        echo.
        echo   ADVERTENCIA: La construccion del frontend fallo.
        echo   El servidor funcionara pero el frontend puede estar desactualizado.
    ) else (
        echo   Frontend construido correctamente.
    )
) else (
    echo   No se encontro frontend, saltando...
)
echo.

REM ============================================
REM  [8] Iniciando servicios
REM ============================================
echo [8/8] Iniciando servicios...

REM Kill old Django on port 8000
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8000.*LISTENING" 2^>nul') do (
    echo   Deteniendo proceso anterior en puerto 8000 (PID %%P^)...
    taskkill /F /PID %%P >nul 2>&1
)
timeout /t 1 >nul

REM Kill old Celery workers
taskkill /FI "WINDOWTITLE eq Celery Worker*" /F >nul 2>&1

REM Start Celery worker
echo   Iniciando Celery worker ^(gevent x3^)...
cd "%DJANGO_DIR%"
start "Celery Worker" cmd /c "cd /d "%DJANGO_DIR%" && set DJANGO_SETTINGS_MODULE=jkanime_vue.settings && "%PYTHON%" -m celery -A jkanime_vue worker --loglevel=info --pool=gevent --concurrency=3"
timeout /t 3 >nul

REM Open browser after a short delay
start "" /b cmd /c "timeout /t 2 >nul && start http://127.0.0.1:8000"

REM Start Django
echo.
echo ============================================
echo   Servidor en http://127.0.0.1:8000
echo   Celery: gevent x3 workers
echo   Presione Ctrl+C para detener
echo ============================================
echo.
"%PYTHON%" manage.py runserver 127.0.0.1:8000
