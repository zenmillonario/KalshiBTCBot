"""Install a separate verified R7 UI. Never patch the frozen engine package.

Only files in this release manifest are copied; an existing destination must be
byte-identical. No process is stopped, no account credential is read, no run starts.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path, PurePosixPath

HERE=Path(__file__).resolve().parent
DEFAULT_LAB=Path(r'C:\KalshiBTCBot_666Lab')
NAME='nautilus_r7_reliability_1_3_0'


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def manifest(root):
    m=json.loads((root/'PACKAGE_MANIFEST.json').read_text(encoding='utf-8'))
    if m.get('product')!='NAUTILUS_R7_RELIABILITY' or m.get('version')!='1.3.0-R7' or m.get('execution_authority') is not False:
        raise ValueError('Wrong UI release identity')
    for rel,expected in m['files_sha256'].items():
        parts=PurePosixPath(rel)
        if parts.is_absolute() or '..' in parts.parts or '\\' in rel or ':' in rel:
            raise ValueError('Unsafe manifest path')
        p=root/rel
        if not p.is_file() or p.is_symlink() or not p.resolve().is_relative_to(root.resolve()) or digest(p)!=expected:
            raise ValueError('Release file missing/modified: '+rel)
    return m


def install(source,lab):
    source=Path(source).resolve();lab=Path(lab).resolve()
    m=manifest(source)
    if not lab.is_dir():
        raise ValueError('Existing Tachys lab directory is missing')
    original=lab/'reassembled_root_audit_r7_4h'/'nautilus'
    expected=json.loads((source/'BASELINE_PROVENANCE.json').read_text(encoding='utf-8'))
    for rel in ('VERSION','adapter.py'):
        p=original/rel
        if not p.is_file() or p.is_symlink() or digest(p)!=expected['sha256'][rel]:
            raise ValueError('Installed integrated R7 Nautilus differs from the inspected baseline: '+rel+'. Nothing replaced.')
    destination=lab/NAME
    files=dict(m['files_sha256'],**{'PACKAGE_MANIFEST.json':digest(source/'PACKAGE_MANIFEST.json')})
    if destination.exists():
        if destination.is_symlink() or not destination.is_dir() or any(not (destination/n).is_file() or (destination/n).is_symlink() or digest(destination/n)!=h for n,h in files.items()):
            raise ValueError('A different installation already exists: '+str(destination)+'. Nothing overwritten.')
        print('PASS identical reliability UI already installed:',destination)
        return destination
    stage=lab/('.nautilus_r7_ui_stage_'+uuid.uuid4().hex)
    stage.mkdir()
    try:
        for rel in files:
            target=stage/rel;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(source/rel,target)
        for rel,h in files.items():
            if digest(stage/rel)!=h:
                raise ValueError('Staging verification failed: '+rel)
        stage.rename(destination)
    finally:
        if stage.exists():
            shutil.rmtree(stage)  # only this install's uniquely created stage
    print('PASS reliability UI installed:',destination)
    print('Original R7 package, engine, snapshot writer and sidecars unchanged.')
    return destination


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--lab',type=Path,default=DEFAULT_LAB)
    p.add_argument('--install-only',action='store_true')
    a=p.parse_args(argv)
    if os.name!='nt':
        raise ValueError('Windows launcher only; install() is separately tested on disposable directories')
    destination=install(HERE,a.lab)
    print('UI-only cache: E-backed run data root / nautilus_cache; health receipt: / nautilus_health')
    print('The first historical backfill can take time. This does not rescan the source on each browser refresh.')
    if not a.install_only:
        # Start only the local UI, and wait so its terminal remains visible.
        return subprocess.call([sys.executable,'-B','-u',str(destination/'nautilus/server.py'),
                                '--lab',str(a.lab),'--build','R7','--port','8580'])
    return 0


if __name__=='__main__':
    try:
        raise SystemExit(main())
    except (OSError,ValueError,KeyError) as exc:
        print('NAUTILUS UI INSTALL DID NOT COMPLETE:',exc,file=sys.stderr)
        print('No engine, snapshot, strategy, or existing UI files were changed.',file=sys.stderr)
        raise SystemExit(1)
