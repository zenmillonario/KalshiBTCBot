@echo off
setlocal DisableDelayedExpansion
title TACHYOS - OPTIONAL EXACT REPLAY OF SAVED PAPER RECORDING
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "TR_ROOT=%~dp0"
cd /d "%TR_ROOT%"
if not exist "%TR_ROOT%complete_paper_run.py" goto incomplete

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
echo.
echo This is an optional offline check of one saved original PAPER recording.
echo It requires the exact program and Python version used for that recording.
echo The original ZIP is already available to send before this check starts.
echo Progress and a separate replay result will be printed; the ZIP is preserved.
echo.
set "TR_ARCHIVE=%~1"
if defined TR_ARCHIVE goto archive_selected
set /p "TR_ARCHIVE=Paste or drag the complete FULL_ORIGINAL ZIP path here, then press Enter: "
if not defined TR_ARCHIVE goto no_archive
:archive_selected
set "TR_ARCHIVE=%TR_ARCHIVE:"=%"
if not exist "%TR_ARCHIVE%" goto no_archive
"%TR_PY%" %TR_PY_ARGS% -X utf8 -u "%TR_ROOT%complete_paper_run.py" --archive "%TR_ARCHIVE%" --replay
set "TR_RC=%ERRORLEVEL%"
echo.
if "%TR_RC%"=="0" echo Exact replay passed. Keep the separate REPLAY_RESULT.json path printed above.
if not "%TR_RC%"=="0" echo Exact replay did not complete with PASS. The original ZIP remains available.
pause
exit /b %TR_RC%

:no_archive
echo An exact existing FULL_ORIGINAL ZIP path is required. No previous run was selected.
goto failed

:incomplete
echo Extract the entire corrected PAPER ZIP to a normal folder before opening this command.
goto failed

:no_python
echo A working Python 3.10 or newer was not found.
echo Use the same Python environment that recorded this PAPER session.

:failed
pause
exit /b 1
