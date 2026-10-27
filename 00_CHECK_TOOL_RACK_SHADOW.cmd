@echo off
setlocal
title TACHYOS TOOL RACK V1 - OFFLINE CHECK
echo ============================================================
echo TACHYOS TOOL RACK V1 - ISOLATED OFFLINE ACCEPTANCE
echo NO R22 ENGINE START - NO PAPER EXECUTION - NO VENUE ORDERS
echo ============================================================
echo.

set "ROOT=%~dp0"
set "PY="
if exist "%ROOT%.venv\Scripts\python.exe" set "PY=%ROOT%.venv\Scripts\python.exe"
if not defined PY if exist "C:\KalshiBTCBot\.venv\Scripts\python.exe" set "PY=C:\KalshiBTCBot\.venv\Scripts\python.exe"
if not defined PY set "PY=python"

"%PY%" "%ROOT%CHECK_TOOL_RACK_V1.py"
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo TOOL RACK OFFLINE CHECK PASSED.
) else (
  echo TOOL RACK OFFLINE CHECK FAILED - DO NOT TRUST SHADOW OUTPUT.
)
pause
exit /b %RC%
