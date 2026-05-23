@echo off
chcp 65001 > nul
title VoiceDrop Setup

:: Python suchen
where python >nul 2>&1
if errorlevel 1 (
    echo FEHLER: Python wurde nicht gefunden.
    echo Bitte installiere Python 3.11+ von https://python.org
    pause
    exit /b 1
)

:: Installer starten
echo Starte VoiceDrop Setup...
python "%~dp0setup.py" %*

if errorlevel 1 (
    echo.
    echo Setup wurde mit einem Fehler beendet.
    pause
)
