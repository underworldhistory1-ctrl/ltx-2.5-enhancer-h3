@echo off
REM ==============================================================================
REM LTX 2.5 Video Enhancement Studio — Windows Launcher
REM ==============================================================================
setlocal enabledelayedexpansion

cd /d "%~dp0"

REM Find python
set "PY=python"
if exist "%~dp0venv\Scripts\python.exe" (
    set "PY=%~dp0venv\Scripts\python.exe"
)

"%PY%" launcher.py %*
pause
