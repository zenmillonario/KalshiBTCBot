@echo off
title Tachyos Command Deck
cd /d "%~dp0"

echo.
echo ==========================================
echo       TACHYOS COMMAND DECK - READ ONLY
echo ==========================================
echo.

python -c "import streamlit, pandas" >nul 2>&1
if errorlevel 1 (
    echo Streamlit or pandas is missing.
    echo.
    echo Run this once:
    echo     python -m pip install -r tachyos_cockpit_requirements.txt
    echo.
    pause
    exit /b 1
)

python -m streamlit run tachyos_cockpit.py
pause
