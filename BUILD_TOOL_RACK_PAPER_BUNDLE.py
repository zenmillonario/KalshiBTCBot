"""Build and verify a strictly whitelisted standalone Tool Rack PAPER archive."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

from CHECK_TOOL_RACK_PAPER import (
    EXCLUDED_LEGACY_TESTS, INSTALLER_VERSIONS, MANIFEST_NAME, MANIFEST_SCHEMA,
    PACKAGE_FILES, TEST_MODULES, audit_package_files,
)


def build(root: Path, output: Path) -> dict:
    root, output = root.resolve(), output.resolve()
    if output.suffix.lower() != ".zip":
        raise ValueError("The delivery output must be a .zip archive")
    audit_package_files(root)
    payloads = {relative: (root / relative).read_bytes() for relative in PACKAGE_FILES}
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "PAPER",
        "strategy_authority": "TOOL_RACK_ONE_COMMANDER",
        "execution_authority": "PASSIVE_PAPER_LEDGER",
        "venue_order_authority": "NONE",
        "simulated_fills_are_venue_fills": False,
        "contains_legacy_r22_engine": False,
        "contains_shadow_runtime": False,
        "starting_cash_usd": "1000.00",
        "installer_versions": INSTALLER_VERSIONS,
        "test_modules": TEST_MODULES,
        "excluded_legacy_test_modules": EXCLUDED_LEGACY_TESTS,
        "files": {
            name: {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
            for name, data in sorted(payloads.items())
        },
    }
    payloads[MANIFEST_NAME] = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="tachyos_paper_bundle_") as temporary:
        staging = Path(temporary)
        archive_path = staging / "delivery.zip"
        extracted = staging / "extracted"
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name, data in sorted(payloads.items()):
                archive.writestr(name, data)
        with zipfile.ZipFile(archive_path, "r") as archive:
            if set(archive.namelist()) != set(payloads):
                raise RuntimeError("Archive file set changed during packaging")
            bad = archive.testzip()
            if bad is not None:
                raise RuntimeError("ZIP integrity failure: " + bad)
            archive.extractall(extracted)
        environment = dict(os.environ)
        environment.pop("PYTHONPATH", None)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        environment["PYTHONUTF8"] = "1"
        print("Checking the actual extracted standalone archive...", flush=True)
        checked = subprocess.run(
            [sys.executable, "-B", "CHECK_TOOL_RACK_PAPER.py", "--require-manifest"],
            cwd=extracted, env=environment, text=True, encoding="utf-8",
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180, check=False,
        )
        print(checked.stdout, end="", flush=True)
        if checked.returncode:
            raise RuntimeError("Extracted standalone package failed CHECK; no delivery archive published")
        # Publish only the complete archive that just passed the extracted check.
        with tempfile.NamedTemporaryFile(prefix=output.stem + "_", suffix=".tmp", dir=output.parent, delete=False) as handle:
            pending = Path(handle.name)
            handle.write(archive_path.read_bytes())
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.replace(pending, output)
        finally:
            pending.unlink(missing_ok=True)
    return {
        "output": str(output),
        "file_count": len(PACKAGE_FILES),
        "manifest": MANIFEST_NAME,
        "zip_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "extracted_check": "PASSED",
        "verified_with_python": sys.version.split()[0],
        "mode": "PAPER",
        "venue_order_authority": "NONE",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--output", type=Path, default=Path("TACHYOS_TOOL_RACK_PAPER_V1.zip"))
    args = parser.parse_args(argv)
    try:
        result = build(args.root, args.output)
    except Exception as exc:
        print(f"BUILD FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
