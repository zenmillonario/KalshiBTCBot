@echo off
title Tachyos V9.5A - Price Freshness / Active Treasury
cd /d C:\KalshiBTCBot
call .venv\Scripts\activate.bat
python -m py_compile tachys_v9_5a_price_freshness_active_treasury.py
if errorlevel 1 (
  echo.
  echo V9.5A compile failed. Do not launch until the error is fixed.
  pause
  exit /b 1
)
echo.
echo ==========================================================
echo  TACHYOS V9.5A - PRICE FRESHNESS / ACTIVE TREASURY
echo  PAPER ONLY - LIMITED NEW PAPER AUTHORITY
echo ==========================================================
echo.
python tachys_v9_5a_price_freshness_active_treasury.py
pause
