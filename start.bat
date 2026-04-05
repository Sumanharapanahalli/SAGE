@echo off
REM ============================================================================
REM SAGE Framework — One-Click Launcher (Windows)
REM
REM Usage:
REM   start.bat                     (default project: starter)
REM   start.bat my_project          (specific project)
REM   start.bat my_project 9000     (custom backend port)
REM ============================================================================

setlocal EnableDelayedExpansion

set "PROJECT=%~1"
if "%PROJECT%"=="" set "PROJECT=starter"

set "PORT=%~2"
if "%PORT%"=="" set "PORT=8000"

set "SAGE_DIR=%~dp0"

echo.
echo   +=======================================+
echo   ^|       SAGE Framework Launcher         ^|
echo   +=======================================+
echo   ^|  Project:  %PROJECT%
echo   ^|  Backend:  http://localhost:%PORT%
echo   ^|  Web UI:   http://localhost:5173
echo   +=======================================+
echo.

REM --- Detect Python venv ---
if exist "%SAGE_DIR%.venv\Scripts\python.exe" (
    set "PYTHON=%SAGE_DIR%.venv\Scripts\python.exe"
) else if exist "%SAGE_DIR%.venv\bin\python" (
    set "PYTHON=%SAGE_DIR%.venv\bin\python"
) else (
    echo ERROR: Virtual environment not found. Run 'make venv' first.
    exit /b 1
)

REM --- Check node_modules ---
if not exist "%SAGE_DIR%web\node_modules" (
    echo Installing web UI dependencies...
    cd /d "%SAGE_DIR%web" && npm install
)

REM --- Start backend ---
echo Starting backend...
set "SAGE_PROJECT=%PROJECT%"
if "%SAGE_SOLUTIONS_DIR%"=="" set "SAGE_SOLUTIONS_DIR=solutions"
start "SAGE Backend" cmd /c "cd /d "%SAGE_DIR%" && "%PYTHON%" src/main.py api --host 0.0.0.0 --port %PORT%"

REM --- Start web UI ---
echo Starting web UI...
start "SAGE Web UI" cmd /c "cd /d "%SAGE_DIR%web" && npm run dev"

echo.
echo SAGE is running. Close this window or the spawned windows to stop.
echo.
echo   Backend:  http://localhost:%PORT%
echo   Web UI:   http://localhost:5173
echo.
pause
