@echo off
title Tachyos V9.4M - Battle Plan / Treasury / Chapter Lab
cd /d C:\KalshiBTCBot
call .venv\Scripts\activate.bat
python -m py_compile tachys_v9_4m_battle_plan_treasury_shadow.py
if errorlevel 1 (
  echo.
  echo V9.4M compile failed. Do not launch until the error is fixed.
  pause
  exit /b 1
)
echo.
echo ===============================================
echo  TACHYOS V9.4M - SHADOW RESEARCH RUN
echo  Frozen V9.4I paper authority
 echo ===============================================
echo.
python tachys_v9_4m_battle_plan_treasury_shadow.py
pause
