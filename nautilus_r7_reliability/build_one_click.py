"""Make a reproducible, self-contained Windows installer from a verified UI folder.

The embedded archive contains only the UI sources and tests, never engine logs.
The Windows wrapper verifies its SHA-256 before extraction and launches only the UI.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED, ZipInfo


def make(source,destination,zip_destination=None):
    source,destination=Path(source),Path(destination)
    manifest=json.loads((source/'PACKAGE_MANIFEST.json').read_text())
    if manifest.get('product')!='NAUTILUS_R7_RELIABILITY' or manifest.get('execution_authority') is not False:
        raise ValueError('Not a read-only Nautilus reliability release')
    buffer=io.BytesIO()
    names=sorted([*manifest['files_sha256'],'PACKAGE_MANIFEST.json'])
    with ZipFile(buffer,'w',ZIP_DEFLATED,compresslevel=9) as z:
        for name in names:
            raw=(source/name).read_bytes()
            expected=manifest['files_sha256'].get(name)
            if expected and hashlib.sha256(raw).hexdigest()!=expected:
                raise ValueError('Modified payload: '+name)
            info=ZipInfo(name,date_time=(2026,10,12,0,0,0))
            info.compress_type=ZIP_DEFLATED;info.external_attr=0o100644<<16
            z.writestr(info,raw)
    raw=buffer.getvalue();h=hashlib.sha256(raw).hexdigest()
    payload=base64.b64encode(raw).decode('ascii')
    payload='\n'.join(payload[n:n+100] for n in range(0,len(payload),100))
    wrapper=r'''@echo off
setlocal
set "PY=C:\KalshiBTCBot\.venv\Scripts\python.exe"
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONUTF8=1"
set "NAUTILUS_SELF=%~f0"
set "NAUTILUS_STAGE=%TEMP%\nautilus_r7_install_%RANDOM%_%RANDOM%"
if not exist "%PY%" (
  echo Existing Python not found: %PY%
  echo Nothing was changed. This installer does not install Python or start the engine.
  pause
  exit /b 1
)
echo THE NAUTILUS 1.3.0-R7 - UI RELIABILITY UPDATE
echo The R7 engine package, snapshot writer and sidecars are NOT replaced or restarted.
powershell -NoProfile -Command "$ErrorActionPreference='Stop'; if(Test-Path -LiteralPath $env:NAUTILUS_STAGE){throw 'Temporary destination already exists'}; $s=[IO.File]::ReadAllText($env:NAUTILUS_SELF); $p=[regex]::Split($s,'(?m)^:NAUTILUS_PAYLOAD\r?$'); if($p.Length -ne 2){throw 'Invalid installer payload'}; $b=[Convert]::FromBase64String($p[1].Trim()); $h=[Security.Cryptography.SHA256]::Create(); try {$v=([BitConverter]::ToString($h.ComputeHash($b))).Replace('-','').ToLowerInvariant()} finally {$h.Dispose()}; if($v -ne '__HASH__'){throw 'Installer hash mismatch'}; [IO.Directory]::CreateDirectory($env:NAUTILUS_STAGE)|Out-Null; $z=Join-Path $env:NAUTILUS_STAGE 'payload.zip'; [IO.File]::WriteAllBytes($z,$b); Expand-Archive -LiteralPath $z -DestinationPath (Join-Path $env:NAUTILUS_STAGE 'release')"
if errorlevel 1 (
  echo Installer preparation failed. No engine or existing UI was changed.
  pause
  exit /b 1
)
"%PY%" -B -u "%NAUTILUS_STAGE%\release\install_ui.py" %*
set "RC=%ERRORLEVEL%"
rem Remove only this wrapper's freshly created temporary unpack folder after normal return.
powershell -NoProfile -Command "if(Test-Path -LiteralPath $env:NAUTILUS_STAGE){Remove-Item -LiteralPath $env:NAUTILUS_STAGE -Recurse -Force}"
echo.
if not "%RC%"=="0" (
  echo Nautilus installer or viewer ended with code %RC%. Preserve the message above.
  echo No engine, snapshot or sidecar process was stopped.
  pause
)
exit /b %RC%
:NAUTILUS_PAYLOAD
__PAYLOAD__
'''
    wrapper=wrapper.replace('__HASH__',h).replace('__PAYLOAD__',payload)
    destination.write_bytes(wrapper.replace('\n','\r\n').encode('ascii'))
    if zip_destination:Path(zip_destination).write_bytes(raw)
    print('Payload ZIP SHA-256:',h)
    print('Self-contained CMD:',destination)
    return h


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--cmd',type=Path,required=True)
    p.add_argument('--zip',type=Path)
    a=p.parse_args();make(a.source,a.cmd,a.zip)
