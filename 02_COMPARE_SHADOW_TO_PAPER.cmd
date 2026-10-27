@echo off
setlocal
title TACHYOS TOOL RACK - SHADOW VS PAPER FORENSICS
echo ============================================================
echo TOOL RACK SHADOW VS LEGACY R22 PAPER
echo READ ONLY - POST/RUN FORENSICS ONLY
echo ============================================================
echo.

set "ROOT=%~dp0"
set "PY="
if exist "%ROOT%.venv\Scripts\python.exe" set "PY=%ROOT%.venv\Scripts\python.exe"
if not defined PY if exist "C:\KalshiBTCBot\.venv\Scripts\python.exe" set "PY=C:\KalshiBTCBot\.venv\Scripts\python.exe"
if not defined PY set "PY=python"

"%PY%" "%ROOT%TOOL_RACK_COMPARE_SHADOW_TO_PAPER.py"
set "RC=%ERRORLEVEL%"

echo.
if "%RC%"=="0" (
  echo Comparison report written under E:\TachyosToolRackShadow\PAPER_...
) else (
  echo Comparison could not be completed. Check that the shadow sidecar and PAPER ledger exist for the same run.
)
pause
exit /b %RC%
