@echo off
REM =============================================================================
REM  START_Book_Studio.bat
REM  Startet book_studio.py im Hintergrund (ohne Konsolenfenster).
REM  Benoetigt: Python 3.x (pythonw.exe im selben Verzeichnis wie python.exe)
REM =============================================================================

REM Arbeitsverzeichnis auf den Skriptordner setzen
cd /d "%~dp0"

REM Pruefen, ob pythonw.exe verfuegbar ist, sonst auf python.exe fallen
set "PY_EXE="
where pythonw >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "PY_EXE=pythonw"
) else (
    where python >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        set "PY_EXE=python"
    ) else (
        echo [FEHLER] Weder pythonw.exe noch python.exe wurde im PATH gefunden.
        echo          Bitte Python 3 installieren und im PATH verfuegbar machen.
        pause
        exit /b 1
    )
)

REM Studio starten
start "" "%PY_EXE%" "%~dp0book_studio.py" %*

exit /b 0
