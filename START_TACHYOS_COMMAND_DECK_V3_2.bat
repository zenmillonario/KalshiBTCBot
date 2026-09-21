@echo off
title Tachyos Command Deck V3.2 - Campaign Cockpit
cd /d C:\KalshiBTCBot

call .venv\Scripts\activate.bat
if errorlevel 1 (
  echo.
  echo Could not activate C:\KalshiBTCBot\.venv
  echo Command Deck V3.2 was NOT launched.
  pause
  exit /b 1
)

python -m py_compile tachyos_command_deck_v3_2.py
if errorlevel 1 (
  echo.
  echo Command Deck V3.2 compile failed.
  pause
  exit /b 1
)

echo.
echo ============================================================
echo  TACHYOS COMMAND DECK V3.2 - CAMPAIGN COCKPIT - READ ONLY
echo ============================================================
echo.

python -m streamlit run tachyos_command_deck_v3_2.py
pause
