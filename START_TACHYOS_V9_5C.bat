@echo off
title Tachyos V9.5C - Leg Geometry / Whole-Leg Authority
cd /d C:\KalshiBTCBot

call .venv\Scripts\activate.bat
if errorlevel 1 (
  echo.
  echo Could not activate C:\KalshiBTCBot\.venv
  echo V9.5C was NOT launched.
  pause
  exit /b 1
)

python -m py_compile tachys_v9_5c_leg_geometry.py
if errorlevel 1 (
  echo.
  echo V9.5C compile failed. Do not launch until the error is fixed.
  pause
  exit /b 1
)

echo.
echo ============================================================
echo  TACHYOS V9.5C - LEG GEOMETRY / WHOLE-LEG AUTHORITY
echo  PAPER ONLY
echo ============================================================
echo.

python -u tachys_v9_5c_leg_geometry.py

echo.
echo Tachyos V9.5C stopped.
pause
