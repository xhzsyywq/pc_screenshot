@echo off
title PC Screenshot Tool
cd /d "%~dp0"
python pc_screenshot.py %*
if errorlevel 1 (
    echo.
    echo [ERROR] Python not found or script failed.
    echo Install Python 3 from https://python.org
    echo.
    pause
)
