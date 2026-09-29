from pathlib import Path
import shutil, json, hashlib, py_compile, subprocess, sys

LAB = Path(r"C:\KalshiBTCBot_666Lab")
SRC = LAB / "observer42"
DST = LAB / "observer42ea1"
EXPECTED_OBS42_IO_SHA = "c1e022e2a6aba7f73111c883f2145ca0eb3957f4e3f670c64b740e4f6ca9d014"
EA1_ENGINE_SHA = "629b42e7c8bed47ae528016adb31fe5b9ecae7c15e92db54a2fc86740c2bf8dd"
ENGINE_NAME = "tachys_v9_5d_666_revival_lab.py"

def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()

print("OBS4.2-EA1 COMPAT INSTALL | OBSERVER ONLY | ENGINE NOT TOUCHED")
if not SRC.is_dir():
    raise SystemExit("STOP: observer42 folder missing.")

manifest_path = SRC / "observer_package_manifest.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
for name, expected in manifest.get("sha256", {}).items():
    p = SRC / name
    if not p.is_file() or sha_bytes(p.read_bytes()) != expected:
        raise SystemExit("STOP: installed observer42 differs from its package manifest: " + name)
if manifest["sha256"].get("commander_io.py") != EXPECTED_OBS42_IO_SHA:
    raise SystemExit("STOP: unexpected observer42 commander_io baseline.")

if DST.exists():
    pm = DST / "observer_package_manifest.json"
    if not pm.is_file():
        raise SystemExit("STOP: observer42ea1 exists but is incomplete; nothing overwritten.")
    print("NOTE  observer42ea1 already exists; verifying rather than replacing.")
else:
    shutil.copytree(SRC, DST)

io_path = DST / "commander_io.py"
text = io_path.read_text(encoding="utf-8")
old = '''def validate_reference(manifest,reference):
    if manifest.get("mode")!="PAPER_ONLY" or manifest.get("source_commit")!=PIN:
        raise ObserverError("Run is not the pinned PAPER reference.")
    if manifest.get("side_action_revision")!=SIDE:
        raise ObserverError("Run is not the verified SIDE1 reference.")
    for key in ("checkpoint_io_revision","quote_policy_revision"):
        if manifest.get(key)!=reference.get(key):raise ObserverError("Reference revision differs: "+key)
    if manifest.get("source_sha256_utf8")!=reference["source_sha256_utf8"]:
        raise ObserverError("Recorded runtime source hashes differ from the frozen one-hour reference.")
'''
new = '''def validate_reference(manifest,reference):
    if manifest.get("mode")!="PAPER_ONLY" or manifest.get("source_commit")!=PIN:
        raise ObserverError("Run is not the pinned PAPER reference.")
    if manifest.get("side_action_revision")!=SIDE:
        raise ObserverError("Run is not the verified SIDE1 reference.")
    for key in ("checkpoint_io_revision","quote_policy_revision"):
        if manifest.get(key)!=reference.get(key):raise ObserverError("Reference revision differs: "+key)
    actual=manifest.get("source_sha256_utf8")
    frozen=reference["source_sha256_utf8"]
    if actual==frozen:
        return
    ea1=dict(frozen)
    ea1["tachys_v9_5d_666_revival_lab.py"]="629b42e7c8bed47ae528016adb31fe5b9ecae7c15e92db54a2fc86740c2bf8dd"
    ea1_ok=(
        actual==ea1
        and manifest.get("version")=="V9.5D-666-EA1-SHADOW-01"
        and manifest.get("hotfix_id")=="666-EA1-SHADOW-01"
        and manifest.get("strategy_parameters_changed") is False
        and str(manifest.get("entry_authority_shadow","")).startswith("EA1 shadow:")
    )
    if not ea1_ok:
        raise ObserverError("Recorded runtime source hashes differ from the frozen HF2 or validated EA1-shadow reference.")
'''
if old in text:
    text = text.replace(old, new, 1)
elif EA1_ENGINE_SHA in text and "validated EA1-shadow reference" in text:
    print("PASS  EA1 compatibility source already installed.")
else:
    raise SystemExit("STOP: expected OBS4.2 validate_reference block not found; nothing changed.")

io_path.write_text(text, encoding="utf-8")
py_compile.compile(str(io_path), doraise=True)

pm_path = DST / "observer_package_manifest.json"
pm = json.loads(pm_path.read_text(encoding="utf-8"))
pm["sha256"]["commander_io.py"] = sha_bytes(io_path.read_bytes())
pm["compatibility"] = "OBS4.2 + validated EA1 shadow runtime source map; observer-only"
pm_path.write_text(json.dumps(pm, indent=2, sort_keys=True) + "\n", encoding="utf-8")

cp = subprocess.run([sys.executable, "-B", str(DST / "run_observer42_tests.py")], cwd=str(DST), check=False)
if cp.returncode:
    raise SystemExit("STOP: OBS4.2-EA1 tests failed. Engine was not touched.")

sys.path.insert(0, str(DST))
import commander_io as cio
ref = json.loads((DST / "frozen_reference.json").read_text(encoding="utf-8"))
base = {
    "mode":"PAPER_ONLY","source_commit":cio.PIN,"side_action_revision":cio.SIDE,
    "checkpoint_io_revision":ref["checkpoint_io_revision"],"quote_policy_revision":ref["quote_policy_revision"],
    "source_sha256_utf8":dict(ref["source_sha256_utf8"]),
}
cio.validate_reference(dict(base), ref)

ea1 = dict(base)
ea1["source_sha256_utf8"] = dict(base["source_sha256_utf8"])
ea1["source_sha256_utf8"][ENGINE_NAME] = EA1_ENGINE_SHA
ea1.update(
    version="V9.5D-666-EA1-SHADOW-01",
    hotfix_id="666-EA1-SHADOW-01",
    strategy_parameters_changed=False,
    entry_authority_shadow="EA1 shadow: Yard restraint + EMA9-parent/Price-child timing + sticky-continuation restraint; ZERO paper authority.",
)
cio.validate_reference(ea1, ref)

bad = dict(ea1)
bad["source_sha256_utf8"] = dict(ea1["source_sha256_utf8"])
bad["source_sha256_utf8"][ENGINE_NAME] = "0"*64
try:
    cio.validate_reference(bad, ref)
except cio.ObserverError:
    pass
else:
    raise SystemExit("STOP: arbitrary runtime-source mutation was not rejected.")

print("PASS  Frozen HF2 reference still accepted.")
print("PASS  Validated EA1 shadow runtime source map accepted.")
print("PASS  Arbitrary source mutation still rejected.")
print("PASS  Original observer42 folder unchanged; observer42ea1 is separate.")
print("OBS4.2-EA1 COMPAT INSTALL COMPLETE - ENGINE NOT RESTARTED")
print(r'Run: "C:\KalshiBTCBot\.venv\Scripts\python.exe" -B -u "C:\KalshiBTCBot_666Lab\observer42ea1\tachys_commander_observer42.py" --watch')
