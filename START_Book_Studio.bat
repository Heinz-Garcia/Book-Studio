@echo off
REM =============================================================================
REM  START_Book_Studio.bat
REM  Startet book_studio.py im Hintergrund (ohne Konsolenfenster).
REM  Bevorzugt die lokale .venv (dort liegen Plugin-Deps wie stylecloud).
REM =============================================================================

cd /d "%~dp0"

set "PY_EXE="

REM 1) Projekt-venv (pythonw bevorzugt, damit kein Konsolenfenster bleibt)
if exist "%~dp0.venv\Scripts\pythonw.exe" (
    set "PY_EXE=%~dp0.venv\Scripts\pythonw.exe"
    goto :run
)
if exist "%~dp0.venv\Scripts\python.exe" (
    set "PY_EXE=%~dp0.venv\Scripts\python.exe"
    goto :run
)

REM 2) Fallback: PATH
where pythonw >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "PY_EXE=pythonw"
    goto :run
)
where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "PY_EXE=python"
    goto :run
)

echo [FEHLER] Kein Python gefunden.
echo          Bitte .venv anlegen ^(python -m venv .venv^) oder Python im PATH.
pause
exit /b 1

:run
start "" "%PY_EXE%" "%~dp0book_studio.py" %*
exit /b 0
