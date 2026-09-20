@echo off
title Tachyos Command Deck V2 - Read Only
cd /d C:\KalshiBTCBot

call .venv\Scripts\activate.bat
if errorlevel 1 (
  echo.
  echo Could not activate C:\KalshiBTCBot\.venv
  echo Command Deck V2 was NOT launched.
  pause
  exit /b 1
)

echo.
echo ============================================================
echo  TACHYOS COMMAND DECK V2 - READ ONLY
echo ============================================================
echo.

python -m streamlit run tachyos_command_deck_v2.py
pause
