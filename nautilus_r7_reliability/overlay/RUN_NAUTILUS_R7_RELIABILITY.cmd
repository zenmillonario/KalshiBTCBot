@echo off
setlocal
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONUTF8=1"
set "PY=C:\KalshiBTCBot\.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo Existing Python environment was not found. Nothing started.
  pause
  exit /b 1
)
"%PY%" -B -u "%~dp0nautilus\server.py" --build R7 --port 8580 %*
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo Nautilus exited with code %RC%. Engine unchanged.
  pause
)
exit /b %RC%
