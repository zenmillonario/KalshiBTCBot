@echo off
setlocal DisableDelayedExpansion
title TACHYOS TOOL RACK - EXPORT STOPPED PAPER RUN
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "TR_ROOT=%~dp0"
cd /d "%TR_ROOT%"
if not exist "%TR_ROOT%TOOL_RACK_EXPORT.py" goto incomplete
set "TR_PY="
set "TR_PY_ARGS="
if exist "%TR_ROOT%.venv\Scripts\python.exe" (
    set "TR_PY=%TR_ROOT%.venv\Scripts\python.exe"
    goto python_ready
)
if exist "C:\KalshiBTCBot\.venv\Scripts\python.exe" (
    set "TR_PY=C:\KalshiBTCBot\.venv\Scripts\python.exe"
    goto python_ready
)
where python >nul 2>&1
if not errorlevel 1 (
    python -c "import sys; raise SystemExit(sys.version_info < (3, 10))" >nul 2>&1
    if not errorlevel 1 (
        set "TR_PY=python"
        goto python_ready
    )
)
where py >nul 2>&1
if not errorlevel 1 (
    py -3 -c "import sys; raise SystemExit(sys.version_info < (3, 10))" >nul 2>&1
    if not errorlevel 1 (
        set "TR_PY=py"
        set "TR_PY_ARGS=-3"
        goto python_ready
    )
)
goto no_python

:python_ready
"%TR_PY%" %TR_PY_ARGS% -X utf8 -c "import sys; raise SystemExit(sys.version_info < (3, 10))" >nul 2>&1
if errorlevel 1 goto no_python
"%TR_PY%" %TR_PY_ARGS% -X utf8 "%TR_ROOT%TOOL_RACK_EXPORT.py" %*
set "TR_RC=%ERRORLEVEL%"
echo.
if not "%TR_RC%"=="0" echo Export failed. Stop the run and review the error above.
pause
exit /b %TR_RC%

:incomplete
echo Extract the entire PAPER ZIP to a normal folder before opening this launcher.
goto failed

:no_python
echo A working Python 3.10 or newer was not found. Python 3.12 or 3.14 is recommended.
echo Install Python or repair the selected local environment, then run 03_INSTALL_TOOL_RACK_DEPENDENCIES.cmd.
goto failed

:failed
echo.
echo The command was not completed. Review the error above; no installation is performed here.
pause
exit /b 1
