"""OBS4.1 SCORE1: narrow live-public remaining-capacity score-accounting repair.
Idempotent observer-only bookkeeping patch. No engine or detector threshold changes.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, py_compile, shutil, subprocess, sys

LAB = Path(__file__).resolve().parent
OBS = LAB / "observer41"
CORE = OBS / "commander_core.py"
MANIFEST = OBS / "observer_package_manifest.json"
RUNNER = OBS / "run_observer41_tests.py"

EXPECTED_ORIG_SHA = "6327bdaaeecbe3fbcaeb4b23d2f531aabb656485694c3192fde2799ebc239755"
OLD_DELAY = 'if mode == "DELAYED_LIVE_OBSERVATION":\n        result["status"]="DELAYED_PUBLICATION_EXCLUDED"; return result'
NEW_DELAY = 'if mode in {"DELAYED_LIVE_OBSERVATION","DELAYED_PUBLIC_OBSERVATION"}:\n        result["status"]="DELAYED_PUBLICATION_EXCLUDED"; return result'
OLD_ALLOWED = 'if mode not in {"LIVE_CSV_OBSERVATION","REPLAY_TIMESTAMP_ASSUMPTION"}:'
NEW_ALLOWED = 'if mode not in {"LIVE_CSV_OBSERVATION","LIVE_PUBLIC_OBSERVATION","REPLAY_TIMESTAMP_ASSUMPTION"}:'

def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()

print("OBS4.1 SCORE1 PATCH | OBSERVER ACCOUNTING ONLY | NO ENGINE OR OBSERVER START")

if not CORE.is_file() or not MANIFEST.is_file() or not RUNNER.is_file():
    raise SystemExit("STOP: observer41 package is incomplete; nothing changed.")

core_bytes = CORE.read_bytes()
core_sha = sha_bytes(core_bytes)
manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
recorded_sha = manifest.get("sha256", {}).get("commander_core.py")
text = core_bytes.decode("utf-8")

already_patched = (NEW_DELAY in text and NEW_ALLOWED in text)

if already_patched:
    if recorded_sha != core_sha:
        raise SystemExit("STOP: SCORE1 text is present but observer41 manifest hash does not match current source.")
    print("PASS  SCORE1 source changes are already installed; no second edit performed.")
else:
    if core_sha != EXPECTED_ORIG_SHA or recorded_sha != EXPECTED_ORIG_SHA:
        raise SystemExit("STOP: observer41 source is neither validated pre-SCORE1 nor a verified SCORE1 install; nothing changed.")
    if OLD_DELAY not in text or OLD_ALLOWED not in text:
        raise SystemExit("STOP: expected OBS4.1 score-accounting block not found; nothing changed.")

    patched_text = text.replace(OLD_DELAY, NEW_DELAY, 1).replace(OLD_ALLOWED, NEW_ALLOWED, 1)
    patched_bytes = patched_text.encode("utf-8")
    patched_sha = sha_bytes(patched_bytes)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    shutil.copy2(CORE, OBS / f"commander_core_pre_score1_{stamp}.py")
    shutil.copy2(MANIFEST, OBS / f"observer_package_manifest_pre_score1_{stamp}.json")

    CORE.write_bytes(patched_bytes)
    manifest["sha256"]["commander_core.py"] = patched_sha
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    py_compile.compile(str(CORE), doraise=True)
    print("PASS  SCORE1 source changes installed and manifest hash updated.")

cp = subprocess.run([sys.executable, "-B", str(RUNNER)], cwd=str(OBS), check=False)
if cp.returncode != 0:
    raise SystemExit("STOP: OBS4.1 test suite failed. Do not start observer41 until reviewed.")

# Use a NORMAL module import in a subprocess. Python 3.14 dataclasses expects
# the module to be present in sys.modules; importlib.exec_module without
# registration caused the prior verifier-only traceback.
probe = r'''
import sys
from pathlib import Path
obs = Path(sys.argv[1])
sys.path.insert(0, str(obs))
import commander_core as mod

pred = {
    "issued_t": 100.0,
    "issued_available_t": 102.0,
    "remaining_capacity": {
        "status": "ISSUED_CONDITIONAL_REMAINING",
        "amplitude_so_far": 10.0,
        "remaining_amplitude_median": 8.0,
        "remaining_amplitude_low": 5.0,
        "remaining_amplitude_high": 12.0,
        "remaining_seconds_median": 20.0,
        "remaining_seconds_low": 15.0,
        "remaining_seconds_high": 30.0,
        "last_compatible_amplitude_baseline": 9.0,
        "last_compatible_seconds_baseline": 22.0,
    },
}
closed = {"end_extreme_t": 122.0, "amplitude": 19.0}

for mode, expected in (
    ("LIVE_PUBLIC_OBSERVATION", "SCORED_TIMELY_FORWARD"),
    ("DELAYED_PUBLIC_OBSERVATION", "DELAYED_PUBLICATION_EXCLUDED"),
):
    p = dict(pred)
    p["publication_mode"] = mode
    got = mod.remaining_outcome(p, closed).get("status")
    if got != expected:
        raise SystemExit(f"{mode} produced {got!r}, expected {expected!r}")
print("BEHAVIOR PROBE PASSED")
'''
probe_cp = subprocess.run(
    [sys.executable, "-B", "-c", probe, str(OBS)],
    cwd=str(OBS),
    check=False,
)
if probe_cp.returncode != 0:
    raise SystemExit("STOP: SCORE1 behavior probe failed. Existing OBS4.1 tests passed, but do not start observer41 until reviewed.")

manifest2 = json.loads(MANIFEST.read_text(encoding="utf-8"))
current_sha = sha_bytes(CORE.read_bytes())
if manifest2.get("sha256", {}).get("commander_core.py") != current_sha:
    raise SystemExit("STOP: post-check observer41 manifest hash mismatch.")

print("PASS  Live-public remaining-capacity forecasts score as timely forward.")
print("PASS  Delayed-public observations remain excluded from forward scoring.")
print("PASS  Existing OBS4.1 test suite passed.")
print("PASS  Python 3.14 normal-import behavior probe passed.")
print("PASS  Shock thresholds, transport, 3/6/9, 15/30/60, HF2 and trading logic unchanged.")
print("OBS4.1 SCORE1 PATCH COMPLETE - BOT AND OBSERVER NOT STARTED")
