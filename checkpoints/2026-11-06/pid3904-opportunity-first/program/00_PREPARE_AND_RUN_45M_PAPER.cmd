@echo off
setlocal DisableDelayedExpansion
title TACHYOS - PREPARE, RECORD 45 MINUTES AND SAVE ORIGINAL
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "TR_ROOT=%~dp0"
cd /d "%TR_ROOT%"
if not exist "%TR_ROOT%TOOL_RACK_PAPER.py" goto incomplete
if not exist "%TR_ROOT%prepare_next_run.py" goto incomplete
if not exist "%TR_ROOT%complete_paper_run.py" goto incomplete
if not exist "%TR_ROOT%post_run_monitor.py" goto incomplete
if not exist "%TR_ROOT%make_upload_parts.py" goto incomplete

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
echo Step 1 of 4: verify the complete package and existing dependency APIs.
set "TR_STAGE=package preflight"
"%TR_PY%" %TR_PY_ARGS% -X utf8 "%TR_ROOT%CHECK_TOOL_RACK_PAPER.py" --preflight-only --require-manifest
if errorlevel 1 goto failed_before_run

echo.
echo Step 2 of 4: check capture, replay and recording capacity on this computer.
set "TR_STAGE=offline recording readiness"
"%TR_PY%" %TR_PY_ARGS% -X utf8 -u "%TR_ROOT%prepare_next_run.py"
if errorlevel 1 goto failed_before_run

set "TR_RECEIPT=%TEMP%\tachyos_next_run_%RANDOM%_%RANDOM%.json"
if exist "%TR_RECEIPT%" goto receipt_exists
echo.
echo Step 3 of 4: start one recorded PAPER engine with a 45-minute entry window.
echo Held positions continue normal strategy management after new entries stop.
echo Automatic drain ends when flat or at the latest held close plus 120 seconds.
echo Ctrl+C requests an orderly flatten; a second Ctrl+C preserves unresolved inventory.
echo This command uses the same Python for preparation, capture and export.
echo It does not install dependencies or submit venue orders.
echo.
"%TR_PY%" %TR_PY_ARGS% -X utf8 -u "%TR_ROOT%TOOL_RACK_PAPER.py" --minutes 45 --record-for-replay --run-receipt "%TR_RECEIPT%"
set "TR_RUN_RC=%ERRORLEVEL%"
if not exist "%TR_RECEIPT%" goto no_new_run

echo.
echo Step 4 of 4: save the complete recording and prepare smaller upload files.
echo The PAPER session is closed. Progress is saved to a log and displayed here.
echo Exact replay is optional and has its own command after the original ZIP is saved.
"%TR_PY%" %TR_PY_ARGS% -X utf8 -u "%TR_ROOT%post_run_monitor.py" --run-receipt "%TR_RECEIPT%"
set "TR_FINISH_RC=%ERRORLEVEL%"
echo.
if "%TR_RUN_RC%"=="2" echo PAPER has unresolved inventory. Keep the evidence and use 05_RECONCILE_PREVIOUS_TOOL_RACK_RUN.cmd before another run.
if not "%TR_RUN_RC%"=="0" if not "%TR_RUN_RC%"=="2" echo PAPER stopped with an error. Keep this window and the printed reports for review.
if not "%TR_FINISH_RC%"=="0" echo Completion needs review. Keep the original folder and the status and ZIP paths printed above.
if "%TR_RUN_RC%"=="0" if "%TR_FINISH_RC%"=="0" echo The recording and upload files are ready. Send 00_SEND_FIRST_REVIEW.zip from the folder that opens.
echo Optional exact replay: open 07_REPLAY_CLOSED_PAPER_RUN.cmd and choose that saved ZIP.
echo Exact run receipt: %TR_RECEIPT%
set "TR_RC=%TR_RUN_RC%"
if "%TR_RC%"=="0" set "TR_RC=%TR_FINISH_RC%"
pause
exit /b %TR_RC%

:no_new_run
echo.
echo No new run receipt was created. Startup was blocked or failed before a new session.
echo No previous run will be replayed or exported by this command.
if "%TR_RUN_RC%"=="0" set "TR_RUN_RC=1"
pause
exit /b %TR_RUN_RC%

:receipt_exists
echo A temporary run receipt already exists. Close this window and start the command again.
goto failed

:incomplete
echo Extract the entire corrected PAPER ZIP to a normal folder before opening this command.
goto failed

:no_python
echo A working Python 3.10 or newer was not found.
echo Repair the selected environment or use 03_INSTALL_TOOL_RACK_DEPENDENCIES.cmd, then try again.
goto failed

:failed_before_run
echo.
echo The %TR_STAGE% step did not pass. The PAPER session was not started.

:failed
echo Keep this window and any printed report paths for review.
pause
exit /b 1
