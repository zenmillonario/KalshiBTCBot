"""Verify exact runtime patch against supplied releases, in memory, without writes.

python -B verify_runtime.py --parent PARENT_1_3_0.zip --candidate HOTFIX_1_3_1.zip
No engine modules are imported, no processes started, no network used.
"""
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

PARENT_SHA='e1d2d2133fceea7cec069889ec3322b5c9ea96d828eca2a018ff39b53cef42c7'
RELEASE_SHA='518da28be8053680c1b47dc031437013e48b230fad719f11f4a8fbb1ecfd21c3'
HERE=Path(__file__).resolve().parent


def digest(raw):return hashlib.sha256(raw).hexdigest()


def verify(parent,candidate):
    if digest(Path(parent).read_bytes())!=PARENT_SHA:raise ValueError('Unexpected parent ZIP')
    if digest(Path(candidate).read_bytes())!=RELEASE_SHA:raise ValueError('Unexpected candidate ZIP')
    changes=json.loads((HERE/'RUNTIME_EDITS.json').read_text())
    with ZipFile(parent) as before,ZipFile(candidate) as after:
        for name,change in changes.items():
            raw=before.read(name)
            if digest(raw)!=change['source_sha256']:raise ValueError('Source differs: '+name)
            lines=raw.decode('utf-8').splitlines(keepends=True)
            last=len(lines)+1
            for edit in reversed(change['edits']):
                start,end=edit['start'],edit['end']
                if not 0<=start<=end<last:raise ValueError('Invalid/overlapping edit range')
                last=start
                lines[start:end]=edit['after'].splitlines(keepends=True)
            result=''.join(lines).encode('utf-8')
            if digest(result)!=change['result_sha256'] or result!=after.read(name):
                raise ValueError('Runtime result differs: '+name)
        manifest=json.loads(after.read('PACKAGE_MANIFEST.json'))
        if manifest.get('version')!='1.3.1-R7' or manifest.get('execution_authority') is not False:
            raise ValueError('Wrong release identity')
        for name,expected in manifest['files_sha256'].items():
            if digest(after.read(name))!=expected:raise ValueError('Release file differs: '+name)
        test_source=(HERE/'tests/test_hotfix131.py').read_bytes()
        if test_source!=after.read('nautilus/tests/test_hotfix131.py'):
            raise ValueError('Git regression tests differ from tested release')
    return {'runtime_files_verified':len(changes),'all_package_files_verified':True,
            'regression_source_matches_release':True,'source_files_written':False}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--parent',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True)
    a=p.parse_args();print(json.dumps(verify(a.parent,a.candidate),indent=2))
