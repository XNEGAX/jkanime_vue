@echo off
chcp 65001 >nul 2>&1
title Jkanime Vue - Gestor de Series
setlocal EnableDelayedExpansion

set "PROJECT_DIR=%~dp0"
set "VENV_DIR=%PROJECT_DIR%venv"
set "NODE_DIR=%PROJECT_DIR%frontend"

echo ============================================
echo   Jkanime Vue - Gestor de Series
echo ============================================
echo.

REM ============================================
REM  [1] Verificando Python
REM ============================================
echo [1/4] Verificando Python...

set "SYS_PYTHON="
where python >nul 2>&1
if %errorlevel% equ 0 (
    for /f "delims=" %%V in ('python --version 2^>^&1') do set "PYVER=%%V"
    echo   Encontrado en PATH: !PYVER!
    set "SYS_PYTHON=python"
    goto :python_ok
)

REM Try common install paths
for %%P in (Python314 Python313 Python312) do (
    if exist "%LOCALAPPDATA%\Programs\Python\%%P\python.exe" (
        set "SYS_PYTHON=%LOCALAPPDATA%\Programs\Python\%%P\python.exe"
        goto :python_found_path
    )
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
set "PATH=%LOCALAPPDATA%\Programs\Python\Python314;%LOCALAPPDATA%\Programs\Python\Python314\Scripts;%PATH%"
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo   Python instalado. Reinicie la consola y vuelva a ejecutar run.bat
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
echo [2/4] Verificando virtualenv...
if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo   Creando virtualenv...
    %SYS_PYTHON% -m venv "%VENV_DIR%"
    if %errorlevel% neq 0 (
        echo.
        echo   ERROR: No se pudo crear el virtualenv.
        pause
        exit /b 1
    )
    echo   Virtualenv creado.
) else (
    echo   Virtualenv ya existe.
)
set "PYTHON=%VENV_DIR%\Scripts\python.exe"
echo.

REM ============================================
REM  [3] Instalando dependencias
REM ============================================
echo [3/4] Instalando dependencias...
%PYTHON% --version >nul 2>&1
if %errorlevel% neq 0 (
    echo   ERROR: Python del virtualenv no funciona. Borre la carpeta venv y reintente.
    pause
    exit /b 1
)
%VENV_DIR%\Scripts\pip.exe install -q -r "%PROJECT_DIR%requirements.txt"
if %errorlevel% neq 0 (
    echo   ERROR: Fallo la instalacion de dependencias.
    pause
    exit /b 1
)
echo   Dependencias OK.
echo.

REM ============================================
REM  [4] Construyendo frontend
REM ============================================
echo [4/4] Verificando frontend...
if exist "%NODE_DIR%\package.json" (
    cd "%NODE_DIR%"
    call npm install --silent 2>nul
    call npm run build --silent 2>nul
    if %errorlevel% neq 0 (
        echo.
        echo   ADVERTENCIA: La construccion del frontend fallo.
    ) else (
        echo   Frontend construido correctamente.
    )
) else (
    echo   No se encontro frontend, saltando...
)
echo.

REM ============================================
REM  Lanzar run.py (Redis, Celery, Django)
REM ============================================
%PYTHON% "%PROJECT_DIR%run.py"

pause
