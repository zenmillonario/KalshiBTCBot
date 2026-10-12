"""Build the one-file Windows runner from the exact, reviewed Python source."""
import base64
import hashlib
from pathlib import Path
import sys


def build(source: Path, destination: Path):
    raw=source.read_bytes()
    digest=hashlib.sha256(raw).hexdigest()
    payload=base64.b64encode(raw).decode('ascii')
    lines='\n'.join(payload[n:n+100] for n in range(0,len(payload),100))
    command=r'''@echo off
setlocal
set "PY=C:\KalshiBTCBot\.venv\Scripts\python.exe"
set "NAUTILUS_SELF=%~f0"
set "NAUTILUS_TEMP=%TEMP%\nautilus_candle_check_%RANDOM%_%RANDOM%.py"
if not exist "%PY%" (
  echo Python not found: %PY%
  echo Nothing was changed. This check does not install Python or start the engine.
  pause
  exit /b 1
)
echo NAUTILUS R7 - LOCAL CANDLE COVERAGE - READ ONLY
echo This does NOT restart or alter the engine, Nautilus or any sidecar.
powershell -NoProfile -Command "$ErrorActionPreference='Stop'; $s=[IO.File]::ReadAllText($env:NAUTILUS_SELF); $p=[regex]::Split($s,'(?m)^:NAUTILUS_PAYLOAD\r?$'); if($p.Length -ne 2){throw 'Invalid checker payload'}; $b=[Convert]::FromBase64String($p[1].Trim()); $h=[Security.Cryptography.SHA256]::Create(); try {$v=([BitConverter]::ToString($h.ComputeHash($b))).Replace('-','').ToLowerInvariant()} finally {$h.Dispose()}; if($v -ne '__HASH__'){throw 'Checker hash mismatch'}; [IO.File]::WriteAllBytes($env:NAUTILUS_TEMP,$b)"
if errorlevel 1 (
  echo The checker could not be prepared. No engine or run files were changed.
  pause
  exit /b 1
)
"%PY%" -B -u "%NAUTILUS_TEMP%" %*
set "RC=%ERRORLEVEL%"
del /q "%NAUTILUS_TEMP%" >nul 2>&1
echo.
if not "%RC%"=="0" echo Check stopped with code %RC%. Preserve the message above.
echo Keep the large snapshot file on E:. Upload only the small report ZIP printed above.
pause
exit /b %RC%
:NAUTILUS_PAYLOAD
__PAYLOAD__
'''
    command=command.replace('__HASH__',digest).replace('__PAYLOAD__',lines)
    destination.write_bytes(command.replace('\n','\r\n').encode('ascii'))
    return digest


if __name__=='__main__':
    dest=Path(sys.argv[1]) if len(sys.argv)>1 else Path('CHECK_NAUTILUS_R7_CANDLES.cmd')
    print('Python payload SHA-256:',build(Path(__file__).with_name('candle_coverage.py'),dest))
