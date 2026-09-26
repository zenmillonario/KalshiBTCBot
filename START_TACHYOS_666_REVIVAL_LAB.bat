@echo off
title Tachyos V9.5D - 666 Revival Lab
cd /d C:\KalshiBTCBot

call .venv\Scripts\activate.bat
if errorlevel 1 (
  echo.
  echo Could not activate C:\KalshiBTCBot\.venv
  echo 666 Revival Lab was NOT launched.
  pause
  exit /b 1
)

python -m py_compile tachys_v9_5d_666_revival_lab.py
if errorlevel 1 (
  echo.
  echo 666 Revival Lab compile failed. Do not launch until fixed.
  pause
  exit /b 1
)

echo.
echo ============================================================
echo  TACHYOS V9.5D - 666 REVIVAL LAB 01
echo  PAPER ONLY - ISOLATED EXPERIMENT
echo ============================================================
echo.

python -u tachys_v9_5d_666_revival_lab.py

echo.
echo Tachyos 666 Revival Lab stopped.
pause
