@echo off
setlocal
rem Fetch a separate UI branch and export ONLY Nautilus. Never checkout/reset/pull the running tree.
set "REPO=C:\KalshiBTCBot"
set "DEST=C:\KalshiBTCBot_666Lab\nautilus_v1_0_0"
set "ARCHIVE=%TEMP%\nautilus_%RANDOM%_%RANDOM%.zip"
if not exist "%REPO%\.git" goto missingrepo
if exist "%DEST%" goto existing
if not exist "C:\KalshiBTCBot_666Lab\." (
  echo Lab directory is missing. Nothing was installed or started.
  goto failed
)
git -C "%REPO%" fetch origin refs/heads/nautilus-v1-readonly
if errorlevel 1 goto failed
git -C "%REPO%" archive --format=zip --output="%ARCHIVE%" FETCH_HEAD nautilus RUN_NAUTILUS.cmd
if errorlevel 1 goto failed
powershell -NoProfile -Command "$ErrorActionPreference='Stop'; Expand-Archive -LiteralPath $env:ARCHIVE -DestinationPath $env:DEST"
if errorlevel 1 goto failed
if not exist "%DEST%\nautilus\server.py" goto failed
del /q "%ARCHIVE%" >nul 2>&1
echo.
echo Nautilus exported to %DEST%
echo Your checked-out branch, strategy, engine and old cockpit were not changed.
call "%DEST%\RUN_NAUTILUS.cmd"
exit /b %ERRORLEVEL%
:existing
echo Nautilus folder already exists: %DEST%
echo Refusing to overwrite or launch an unverified existing installation.
echo Use its RUN_NAUTILUS.cmd to reopen an installation you have already verified.
goto failed
:missingrepo
echo Git repository not found at %REPO%. No files were changed.
:failed
echo.
echo Nautilus did not start. Preserve the message above. No engine was changed.
pause
exit /b 1
