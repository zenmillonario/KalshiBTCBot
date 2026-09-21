@echo off
title Tachyos V9.5D - Campaign Authority / Winner Harvest
cd /d C:\KalshiBTCBot

call .venv\Scripts\activate.bat
if errorlevel 1 (
  echo.
  echo Could not activate C:\KalshiBTCBot\.venv
  echo V9.5D was NOT launched.
  pause
  exit /b 1
)

python -m py_compile tachys_v9_5d_campaign_authority.py
if errorlevel 1 (
  echo.
  echo V9.5D compile failed. Do not launch until fixed.
  pause
  exit /b 1
)

echo.
echo ============================================================
echo  TACHYOS V9.5D - CAMPAIGN AUTHORITY / WINNER HARVEST
echo  PAPER ONLY
echo ============================================================
echo.

python -u tachys_v9_5d_campaign_authority.py

echo.
echo Tachyos V9.5D stopped.
pause
