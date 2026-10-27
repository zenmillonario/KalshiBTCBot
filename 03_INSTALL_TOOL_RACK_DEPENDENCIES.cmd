@echo off
setlocal DisableDelayedExpansion
title TACHYOS TOOL RACK - EXPLICIT LOCAL DEPENDENCY INSTALL
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "TR_ROOT=%~dp0"
cd /d "%TR_ROOT%"
if not exist "%TR_ROOT%requirements_tool_rack_paper.txt" goto incomplete
if exist "%TR_ROOT%.venv\Scripts\python.exe" goto install_local
set "TR_PY="
set "TR_PY_ARGS="
if exist "C:\KalshiBTCBot\.venv\Scripts\python.exe" (
    set "TR_PY=C:\KalshiBTCBot\.venv\Scripts\python.exe"
    goto create_local
)
where python >nul 2>&1
if not errorlevel 1 (
    python -c "import sys; raise SystemExit(sys.version_info < (3, 10))" >nul 2>&1
    if not errorlevel 1 (
        set "TR_PY=python"
        goto create_local
    )
)
where py >nul 2>&1
if not errorlevel 1 (
    py -3 -c "import sys; raise SystemExit(sys.version_info < (3, 10))" >nul 2>&1
    if not errorlevel 1 (
        set "TR_PY=py"
        set "TR_PY_ARGS=-3"
        goto create_local
    )
)
goto no_python

:create_local
"%TR_PY%" %TR_PY_ARGS% -X utf8 -c "import sys; raise SystemExit(sys.version_info < (3, 10))" >nul 2>&1
if errorlevel 1 goto no_python
echo Creating a bundle-local environment. The existing KalshiBTCBot environment is not modified.
"%TR_PY%" %TR_PY_ARGS% -X utf8 -m venv "%TR_ROOT%.venv"
if errorlevel 1 goto failed

:install_local
echo.
echo This explicit installer downloads the pinned PAPER dependencies into this bundle's .venv.
"%TR_ROOT%.venv\Scripts\python.exe" -X utf8 -m pip install --disable-pip-version-check --upgrade pip
if errorlevel 1 goto failed
"%TR_ROOT%.venv\Scripts\python.exe" -X utf8 -m pip install --disable-pip-version-check -r "%TR_ROOT%requirements_tool_rack_paper.txt"
if errorlevel 1 goto failed
"%TR_ROOT%.venv\Scripts\python.exe" -X utf8 "%TR_ROOT%CHECK_TOOL_RACK_PAPER.py"
set "TR_RC=%ERRORLEVEL%"
echo.
if "%TR_RC%"=="0" echo Dependencies installed and offline PAPER checks passed. Use 01_START_TOOL_RACK_PAPER_90M.cmd when ready.
if not "%TR_RC%"=="0" echo Installation finished but CHECK failed. Review its output before starting.
pause
exit /b %TR_RC%

:incomplete
echo Extract the entire PAPER ZIP to a writable folder before installing dependencies.
goto failed

:no_python
echo A working Python 3.10 or newer was not found. Install Python 3.12 or 3.14, then rerun this installer.
goto failed

:failed
echo.
echo Installation or verification failed. The existing KalshiBTCBot environment has not been changed.
echo Keep the error above. Confirm the bundle folder is writable and internet access is available.
pause
exit /b 1
