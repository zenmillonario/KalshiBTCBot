@echo off
title Tachyos Command Deck

cd /d "%~dp0"

echo.
echo ==========================================
echo       TACHYOS COMMAND DECK - READ ONLY
echo ==========================================
echo.

call .venv\Scripts\activate.bat

python -m streamlit run tachyos_cockpit.py

pause