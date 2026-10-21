import hashlib
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('ui_installer',ROOT/'install_ui.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.source=self.root/'source';self.source.mkdir()
        self.lab=self.root/'lab';self.lab.mkdir()
        original=self.lab/'reassembled_root_audit_r7_4h'/'nautilus';original.mkdir(parents=True)
        self.original=original
        (original/'adapter.py').write_text('baseline adapter')
        (original/'VERSION').write_text('1.2.0-R7\n')
        (self.source/'nautilus').mkdir()
        (self.source/'nautilus/server.py').write_text('viewer only')
        provenance={'sha256':{n:mod.digest(original/n) for n in ('adapter.py','VERSION')}}
        (self.source/'BASELINE_PROVENANCE.json').write_text(json.dumps(provenance))
        self.m=dict(product='NAUTILUS_R7_RELIABILITY',version='1.3.0-R7',execution_authority=False,
                    files_sha256={str(p.relative_to(self.source)):mod.digest(p) for p in self.source.rglob('*') if p.is_file()})
        self.save()
    def save(self):
        (self.source/'PACKAGE_MANIFEST.json').write_text(json.dumps(self.m))
    def test_install_separate_preserves_original(self):
        before={p.name:mod.digest(p) for p in self.original.iterdir()}
        dest=mod.install(self.source,self.lab)
        self.assertEqual(dest.name,mod.NAME)
        self.assertEqual(before,{p.name:mod.digest(p) for p in self.original.iterdir()})
    def test_identical_reinstall_is_safe(self):
        a=mod.install(self.source,self.lab);b=mod.install(self.source,self.lab);self.assertEqual(a,b)
    def test_modified_destination_refused(self):
        dest=mod.install(self.source,self.lab);(dest/'nautilus/server.py').write_text('changed')
        with self.assertRaises(ValueError):mod.install(self.source,self.lab)
        self.assertEqual((dest/'nautilus/server.py').read_text(),'changed')
    def test_modified_payload_refused(self):
        (self.source/'nautilus/server.py').write_text('changed')
        with self.assertRaises(ValueError):mod.install(self.source,self.lab)
    def test_wrong_baseline_refused(self):
        (self.original/'adapter.py').write_text('different build')
        with self.assertRaises(ValueError):mod.install(self.source,self.lab)
        self.assertFalse((self.lab/mod.NAME).exists())
    def test_path_traversal_refused(self):
        self.m['files_sha256']['../escaped']='foo';self.save()
        with self.assertRaises(ValueError):mod.install(self.source,self.lab)
    def test_wrong_release_identity_refused(self):
        self.m['execution_authority']=True;self.save()
        with self.assertRaises(ValueError):mod.install(self.source,self.lab)
    def test_missing_lab_refused(self):
        with self.assertRaises(ValueError):mod.install(self.source,self.root/'missing')

if __name__=='__main__':unittest.main()
