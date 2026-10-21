@echo off
setlocal
rem UI-only export. No checkout, reset, merge, strategy change or engine restart.
set "REPO=C:\KalshiBTCBot"
set "DEST=C:\KalshiBTCBot_666Lab\nautilus_v1_1_0"
set "ARCHIVE=%TEMP%\nautilus_bridge_%RANDOM%_%RANDOM%.zip"
set "VERSION_FILE=%TEMP%\nautilus_version_%RANDOM%_%RANDOM%.txt"
if not exist "%REPO%\.git" goto missingrepo
if exist "%DEST%" goto existing
if not exist "C:\KalshiBTCBot_666Lab\." (
  echo Lab directory is missing. Nothing was installed or started.
  goto failed
)
git -C "%REPO%" fetch origin refs/heads/nautilus-v1-readonly
if errorlevel 1 goto failed
for /f "delims=" %%H in ('git -C "%REPO%" rev-parse FETCH_HEAD') do set "REVISION=%%H"
if not defined REVISION goto failed
git -C "%REPO%" show "%REVISION%:nautilus/VERSION" > "%VERSION_FILE%"
if errorlevel 1 goto failed
set /p "ACTUAL_VERSION=" < "%VERSION_FILE%"
del /q "%VERSION_FILE%" >nul 2>&1
if not "%ACTUAL_VERSION%"=="1.1.0" (
  echo This installer requires Nautilus 1.1.0. Get the installer matching the Git release.
  goto failed
)
git -C "%REPO%" archive --format=zip --output="%ARCHIVE%" "%REVISION%" nautilus RUN_NAUTILUS.cmd
if errorlevel 1 goto failed
powershell -NoProfile -Command "$ErrorActionPreference='Stop'; Expand-Archive -LiteralPath $env:ARCHIVE -DestinationPath $env:DEST"
if errorlevel 1 goto failed
if not exist "%DEST%\nautilus\server.py" goto failed
del /q "%ARCHIVE%" >nul 2>&1
echo.
echo THE NAUTILUS 1.1.0 - BRIDGE LAYOUT
echo Installed: %DEST%
echo Git revision: %REVISION%
echo Your engine, old Nautilus folder, cockpit and working branch were not changed.
call "%DEST%\RUN_NAUTILUS.cmd" %*
exit /b %ERRORLEVEL%
:existing
echo Nautilus folder already exists: %DEST%
echo Refusing to overwrite or launch an unverified existing installation.
echo To reopen a verified install, call its RUN_NAUTILUS.cmd.
goto failed
:missingrepo
echo Git repository not found at %REPO%. No files were changed.
:failed
echo.
echo Nautilus did not start. Preserve the message above. No engine was changed.
pause
exit /b 1
