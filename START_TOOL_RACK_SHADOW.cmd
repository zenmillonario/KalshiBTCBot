@echo off
setlocal
title TACHYOS TOOL RACK SHADOW - READ ONLY
echo ============================================================
echo TACHYOS TOOL RACK V1 - LIVE SHADOW SIDECAR
echo READ ONLY - NO PAPER OR VENUE EXECUTION AUTHORITY
echo Reads an existing R22 PAPER run only.
echo Writes only to E:\TachyosToolRackShadow by default.
echo ============================================================
echo.

set "ROOT=%~dp0"
set "PY="

if exist "%ROOT%.venv\Scripts\python.exe" set "PY=%ROOT%.venv\Scripts\python.exe"
if not defined PY if exist "C:\KalshiBTCBot\.venv\Scripts\python.exe" set "PY=C:\KalshiBTCBot\.venv\Scripts\python.exe"
if not defined PY set "PY=python"

"%PY%" "%ROOT%TOOL_RACK_ATTACH_R22_SHADOW.py"
set "RC=%ERRORLEVEL%"

echo.
echo Tool Rack shadow ended with code %RC%.
echo No PAPER strategy or exchange order was authorized by this sidecar.
pause
exit /b %RC%
