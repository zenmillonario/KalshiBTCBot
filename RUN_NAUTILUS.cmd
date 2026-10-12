@echo off
setlocal
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONUTF8=1"
set "NAUTILUS_PYTHON="
if exist "C:\KalshiBTCBot\.venv\Scripts\python.exe" set "NAUTILUS_PYTHON=C:\KalshiBTCBot\.venv\Scripts\python.exe"
if not exist "%~dp0nautilus\server.py" (
  echo Nautilus installation is incomplete. No engine was changed.
  pause
  exit /b 1
)
if defined NAUTILUS_PYTHON (
  "%NAUTILUS_PYTHON%" -B "%~dp0nautilus\server.py" %*
) else (
  py -3 "%~dp0nautilus\server.py" %*
)
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo.
  echo Nautilus stopped with code %RC%. Preserve the message above.
  echo The engine and old cockpit were not changed.
  pause
)
exit /b %RC%
