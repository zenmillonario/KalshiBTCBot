"""Rebuild the exact UI-only release from the verified integrated R7 baseline.

Use the original R7 release ZIP or extracted root, not the older Git 1.1 UI.
Reads only; writes a new destination. Does not execute/import any baseline code.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

HERE=Path(__file__).resolve().parent


def safe_name(name):
    parts=PurePosixPath(name)
    if parts.is_absolute() or '..' in parts.parts or ':' in name or '\\' in name:
        raise ValueError('Unsafe release path')
    return parts


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def build(baseline, output):
    baseline,output=Path(baseline).resolve(),Path(output).resolve()
    if output.exists():
        raise ValueError('Destination exists; never overwrite a release or engine directory')
    if baseline.is_dir() and (output==baseline or baseline in output.parents):
        raise ValueError('Output must be outside the original R7 package')
    provenance=json.loads((HERE/'BASELINE_PROVENANCE.json').read_text())
    expected=json.loads((HERE/'RELEASE_FILES.json').read_text())
    edits=json.loads((HERE/'source_edits.json').read_text())
    archive=ZipFile(baseline) if baseline.is_file() else None
    try:
        def original(name):
            safe_name(name)
            if archive:
                info=archive.getinfo(name)
                if info.file_size>4_000_000:
                    raise ValueError('Unexpected large source file')
                return archive.read(info)
            source=baseline/name
            if source.is_symlink() or not source.resolve().is_relative_to(baseline):
                raise ValueError('Invalid source path')
            return source.read_bytes()
        # Check every inspected R7 UI input, not just the files changed here.
        for rel,h in provenance['sha256'].items():
            if digest(original('nautilus/'+rel))!=h:
                raise ValueError('R7 baseline differs: '+rel)
        files={}
        for rel,h in expected.items():
            safe_name(rel)
            overlay=HERE/'overlay'/rel
            if overlay.is_file():
                raw=overlay.read_bytes()
            else:
                raw=original(rel)
                change=edits.get(rel)
                if change:
                    if digest(raw)!=change['source_sha256']:
                        raise ValueError('Unexpected patch source: '+rel)
                    text=raw.decode('utf-8').replace('\r\n','\n').splitlines(keepends=True)
                    for op in reversed(change['edits']):
                        a,b=op['start'],op['end']
                        if ''.join(text[a:b])!=op['before']:
                            raise ValueError('Patch context mismatch: '+rel)
                        text[a:b]=op['after'].splitlines(keepends=True)
                    raw=''.join(text).encode('utf-8')
            if digest(raw)!=h:
                raise ValueError('Final release hash differs: '+rel)
            files[rel]=raw
        manifest={'product':'NAUTILUS_R7_RELIABILITY','version':'1.3.0-R7',
                  'execution_authority':False,'baseline':'1.2.0-R7','files_sha256':expected}
        files['PACKAGE_MANIFEST.json']=(json.dumps(manifest,indent=2)+'\n').encode()
        output.mkdir(parents=True,exist_ok=False)
        for rel,raw in files.items():
            target=output/rel;target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(raw)
        print('PASS exact UI release reconstructed:',output)
        return output
    finally:
        if archive:archive.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    build(a.baseline,a.out)
