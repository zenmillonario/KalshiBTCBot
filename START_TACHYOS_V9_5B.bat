@echo off
title Tachyos V9.5B - Level-2 Battle Council / Thesis Shield
cd /d C:\KalshiBTCBot

call .venv\Scripts\activate.bat
if errorlevel 1 (
  echo.
  echo Could not activate C:\KalshiBTCBot\.venv
  echo V9.5B was NOT launched.
  pause
  exit /b 1
)

python -m py_compile tachys_v9_5b_level2_intermission_thesis_shield.py
if errorlevel 1 (
  echo.
  echo V9.5B compile failed. Do not launch until the error is fixed.
  pause
  exit /b 1
)

echo.
echo ============================================================
echo  TACHYOS V9.5B - LEVEL-2 BATTLE COUNCIL / THESIS SHIELD
echo  PAPER ONLY
echo ============================================================
echo.

python -u tachys_v9_5b_level2_intermission_thesis_shield.py

echo.
echo Tachyos V9.5B stopped.
pause
