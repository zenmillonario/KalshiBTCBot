"""Build and verify a strictly whitelisted standalone Tool Rack PAPER archive."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile
import zipfile

from CHECK_TOOL_RACK_PAPER import (
    EXCLUDED_LEGACY_TESTS, INSTALLER_VERSIONS, MANIFEST_NAME, MANIFEST_SCHEMA, RELEASE_ID,
    BASELINE_PACKAGE_SHA256, CAPTURE_TEST_MODULES, PACKAGE_FILES, TEST_MODULES,
    audit_package_files, verify_frozen_source, verify_authorized_delta,
    APPROVED_CORRECTIONS, PREVIOUS_PACKAGE_SHA256, APPROVED_CHANGED_CORE_FILES, APPROVED_ADDED_CORE_FILES,
)
from strategy_core.nautilus_projection import VERSION as DASHBOARD_REVISION
from strategy_core.paper_runtime import RUNTIME_REVISION


PID3904_DECISIONS_SHA256 = "da03d3ff02f8d718670212d93606df39a126f70a65b96d26a360776c108e4506"
PID3904_TAPE_SHA256 = "8949f50fbde0c06a8d853e3a2c061657dc219beaf3c151e88410dfb78d133c5d"
ENGINE_CONSTRUCT_CONTROLS = frozenset({
    "all_original_calls_executed", "all_source_frame_identities_preserved",
    "fresh_model_sequence_has_positive_admission", "every_entry_has_positive_commander_species",
    "original_negative_source_frame_2932", "original_negative_source_frame_3192",
    "original_negative_source_frame_6295", "original_negative_source_frame_6466",
    "fresh_inventory_and_custody_exercised", "whole_lot_model_exits", "no_venue_fill_claim",
})


def verify_engine_construct_receipt(root: Path, source: dict[str, str]) -> dict:
    """Require the completed source-bound full-recording Construct before release.

    The large original recording and generated trace live in the separate
    evidence archive. This receipt is created by the actual driver and its
    semantic inspector, then bound to the exact packaged source and driver.
    Extracted engineering checks run again below on byte-identical source.
    """
    report = json.loads((root / "OPPORTUNITY_FIRST_ENGINE_CONSTRUCT.json").read_text(encoding="utf-8"))
    baseline = json.loads((root / "PID3904_SOURCE_SHA256.json").read_text(encoding="utf-8"))
    driver_sha = hashlib.sha256((root / "CONSTRUCT_OPPORTUNITY_FIRST_ENGINE_SEQUENCE.py").read_bytes()).hexdigest()
    checks = report.get("semantic_controls") or []
    check_names = {item.get("name") for item in checks}
    hashes = ("trace_sha256", "construct_decisions_sha256", "original_decision_chain_sha256",
              "construct_decision_chain_sha256")
    if (report.get("schema") != "tachyos.opportunity_first_engine_construct.v1"
            or report.get("complete") is not True or report.get("pass_semantic") is not True
            or report.get("error") is not None or report.get("source_changed_during_construct") is not False
            or report.get("candidate_source_sha256") != source
            or report.get("baseline_source_sha256") != baseline
            or report.get("construct_driver_sha256") != driver_sha
            or report.get("recorded_decisions_sha256") != PID3904_DECISIONS_SHA256
            or report.get("recorded_tape_sha256") != PID3904_TAPE_SHA256
            or report.get("source_run") != "TOOL_RACK_PAPER_20261106T121055Z_PID3904"
            or report.get("call_count") != 6965 or report.get("frame_count") != 6963
            or report.get("method_counts") != {"init": 1, "process": 6963, "close": 1}
            or report.get("scope") != "CHRONOLOGICAL_MODIFIED_ENGINE_CONSTRUCT"
            or report.get("exact_engine_replay") is not False
            or report.get("actual_captured_feed_book_arguments_unchanged") is not True
            or report.get("fresh_candidate_engine_and_inventory") is not True
            or report.get("profit_claim") is not False
            or not ENGINE_CONSTRUCT_CONTROLS.issubset(check_names)
            or len(check_names) != len(checks) or not all(item.get("pass") is True for item in checks)
            or not report.get("entry_admissions") or not report.get("model_entries")
            or not report.get("model_exits") or not report.get("custody_reasons")
            or not all(re.fullmatch(r"[0-9a-f]{64}", str(report.get(key, ""))) for key in hashes)):
        raise RuntimeError("Current-source complete Opportunity-First engine Construct gate has not passed")
    return report


def build(root: Path, output: Path, *, capture_candidate: bool = False) -> dict:
    if capture_candidate:
        raise ValueError("Approved strategy corrections require the full strategy, capture and replay gate")
    root, output = root.resolve(), output.resolve()
    if output.suffix.lower() != ".zip":
        raise ValueError("The delivery output must be a .zip archive")
    audit_package_files(root)
    frozen_count = verify_frozen_source(root)
    approved_delta = verify_authorized_delta(root)
    source = json.loads((root / "SOURCE_SHA256.json").read_text(encoding="utf-8"))
    sequence_audit = json.loads((root / "OPPORTUNITY_FIRST_SEQUENCE_AUDIT.json").read_text(encoding="utf-8"))
    if (sequence_audit.get("pass") is not True
            or sequence_audit.get("candidate_source_sha256") != source
            or sequence_audit.get("baseline_source_sha256") !=
                json.loads((root / "PID3904_SOURCE_SHA256.json").read_text(encoding="utf-8"))
            or sequence_audit.get("frame_count") != 6963
            or sequence_audit.get("recorded_decisions_sha256") != PID3904_DECISIONS_SHA256
            or sequence_audit.get("per_frame_report") != "OPPORTUNITY_FIRST_SEQUENCE_FRAMES.jsonl.gz"
            or sequence_audit.get("per_frame_report_sha256") != hashlib.sha256(
                (root / "OPPORTUNITY_FIRST_SEQUENCE_FRAMES.jsonl.gz").read_bytes()).hexdigest()):
        raise RuntimeError("Current-source Opportunity-First behavioral sequence gate has not passed")
    engine_construct = verify_engine_construct_receipt(root, source)
    payloads = {relative: (root / relative).read_bytes() for relative in PACKAGE_FILES}
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "release_id": RELEASE_ID,
        "runtime_revision": RUNTIME_REVISION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "PAPER",
        "strategy_authority": "ONE_COMMANDER_AUTHORIZED_MOUNTAIN_RELEASE_RAIL_HEIST",
        "execution_authority": "PASSIVE_PAPER_LEDGER",
        "dashboard": "THE_NAUTILUS_TOOL_RACK",
        "dashboard_revision": DASHBOARD_REVISION,
        "recommended_launcher": "00_PREPARE_AND_RUN_45M_PAPER.cmd",
        "recommended_entry_window_minutes": 45,
        "default_entry_window_minutes": 45,
        "legacy_direct_cli_default_minutes": 360,
        "post_run_default": "VERIFY_COMPLETE_ORIGINAL_THEN_CREATE_SMALL_UPLOADS",
        "post_run_replay": "EXPLICIT_OPTIONAL_07_COMMAND",
        "engineering_candidate": False,
        "strategy_modified": True,
        "strategy_parameters_changed_by_this_repair": True,
        "runtime_repair": "PID3904_OPPORTUNITY_FIRST_COMMANDER_WITH_CAUSAL_WATCHES",
        "captured_baseline_archive_sha256": "ef711c357a903e0c39d20b2b9179d8c8b7aa00a2ba8febb8f89ed716261d78b6",
        "approved_strategy_corrections": APPROVED_CORRECTIONS,
        "baseline_package_sha256": BASELINE_PACKAGE_SHA256,
        "previous_package_sha256": PREVIOUS_PACKAGE_SHA256,
        "sealed_strategy_config_ui_files": frozen_count,
        "changed_core_files": sorted(APPROVED_CHANGED_CORE_FILES),
        "added_core_files": sorted(APPROVED_ADDED_CORE_FILES),
        "unchanged_previous_strategy_config_ui_files": approved_delta["unchanged_files"],
        "historical_approval_preserved": True,
        "windows_runtime_verified": False,
        "six_hour_capture_accepted": False,
        "profitability_proven": False,
        "delivery_gate": "FULL_RECORDED_SEQUENCE_ENGINE_CONSTRUCT_EXTRACTED_CHECK_CAPTURE_JS_REPLAY_FINAL_INTEGRITY",
        "capture_test_modules": CAPTURE_TEST_MODULES,
        "automatic_cutoff_action": "STOP_NEW_ENTRIES_CONTINUE_HELD_STRATEGY",
        "default_finality_buffer_after_latest_held_close_seconds": 120,
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
        # Write the nested acceptance output to a real file rather than a PIPE.
        # Some acceptance modules spawn helper processes; a grandchild that
        # inherits a pipe descriptor can keep subprocess.communicate() waiting
        # after the checker itself has already exited.  A file preserves the
        # complete audit transcript without that descriptor-lifetime hazard.
        check_log = staging / "extracted_check.log"
        commands = [
            [sys.executable, "-B", "CHECK_TOOL_RACK_PAPER.py", "--require-manifest", "--workers", "3"],
            *([sys.executable, "-B", "-m", "unittest", "-q", module]
              for module in CAPTURE_TEST_MODULES),
            [sys.executable, "-B", "RUN_PID10656_LOOKING_GLASS_CONSTRUCT.py", "--with-js"],
            [sys.executable, "-B", "run_validation.py", "--out", str(staging / "three_way_proof")],
        ]
        with check_log.open("w", encoding="utf-8", newline="") as log:
            for command in commands:
                print("Delivery gate: " + " ".join(command[2:]), flush=True)
                log.write("Extracted check: " + " ".join(command[2:]) + "\n")
                log.flush()
                checked = subprocess.run(
                    command, cwd=extracted, env=environment, text=True, encoding="utf-8",
                    stdout=log, stderr=subprocess.STDOUT,
                    timeout=1800 if "CHECK_TOOL_RACK_PAPER.py" in command else 300, check=False,
                )
                if checked.returncode:
                    break
        checked_output = check_log.read_text(encoding="utf-8")
        print(checked_output, end="", flush=True)
        if checked.returncode:
            raise RuntimeError("Extracted standalone package failed CHECK; no delivery archive published")
        declared = re.search(r"^Running (\d+) tests in (\d+) isolated modules\.$", checked_output, re.MULTILINE)
        completed = re.search(r"^CHECK PASSED: (\d+) current tests .*PID10656 Looking Glass Constructs\.", checked_output, re.MULTILINE)
        if (declared is None or completed is None
                or int(declared.group(2)) != len(TEST_MODULES)
                or int(completed.group(1)) != int(declared.group(1))
                or "PID17224 APPROVED CORRECTIONS CONSTRUCT PASS" not in checked_output
                or "PID19996 RAIL VALUE CONSTRUCT PASS" not in checked_output
                or "PID4596 RUNTIME REPAIR CONSTRUCT PASS" not in checked_output
                or "PID17588 LATE SCOUT CONSTRUCT PASS" not in checked_output
                or "PID15184 CURRENT PARENT CALIBRATION CONSTRUCT PASS" not in checked_output
                or "PID4824 RECOVERY IDENTITY CONSTRUCT PASS" not in checked_output
                or "PID4824 FLOOR AUTHORITY CONSTRUCT PASS" not in checked_output
                or "PID10656 SPROUT HEIST CONSTRUCT PASS" not in checked_output
                or "PID10656_LOOKING_GLASS_CONSTRUCT_PASS" not in checked_output
                or "PID14048 QUOTE VALUE AND STALL CONSTRUCT PASS" not in checked_output):
            raise RuntimeError("Extracted CHECK did not report every mandatory gate; no archive published")
        capture_counts = {}
        for module in CAPTURE_TEST_MODULES:
            marker = "Extracted check: -m unittest -q " + module + "\n"
            if marker not in checked_output:
                raise RuntimeError("Capture module command missing from check log: " + module)
            section = checked_output.split(marker, 1)[1]
            section = section.split("Extracted check:", 1)[0]
            count = re.search(r"^Ran (\d+) tests? in ", section, re.MULTILINE)
            if count is None or int(count.group(1)) < 1 or not re.search(r"^OK\s*$", section, re.MULTILINE):
                raise RuntimeError("Capture test module did not pass: " + module)
            capture_counts[module] = int(count.group(1))
        proof_path = staging / "three_way_proof" / "validation_report.json"
        proof = json.loads(proof_path.read_text(encoding="utf-8"))
        if proof.get("pass") is not True:
            raise RuntimeError("Fresh approved-build three-way replay proof failed")
        construct = json.loads((extracted / "PID17224_APPROVED_CORRECTIONS_CONSTRUCT_RESULTS" / "report.json").read_text(encoding="utf-8"))
        rail_construct = json.loads((extracted / "PID19996_RAIL_VALUE_CONSTRUCT_RESULTS" / "report.json").read_text(encoding="utf-8"))
        if rail_construct.get("passed") is not True:
            raise RuntimeError("Recorded PID19996 rail fishing Construct did not pass")
        repair_construct = json.loads((extracted / "PID4596_RUNTIME_REPAIR_CONSTRUCT_RESULTS" / "report.json").read_text(encoding="utf-8"))
        if repair_construct.get("passed") is not True:
            raise RuntimeError("PID4596 runtime repair Construct did not pass")
        scout_construct = json.loads((extracted / "PID17588_LATE_SCOUT_CONSTRUCT_RESULTS" / "report.json").read_text(encoding="utf-8"))
        if scout_construct.get("passed") is not True:
            raise RuntimeError("PID17588 late-scout Construct did not pass")
        current_parent_construct = json.loads((extracted / "PID15184_CURRENT_PARENT_CALIBRATION_CONSTRUCT_RESULTS" / "report.json").read_text(encoding="utf-8"))
        if current_parent_construct.get("passed") is not True:
            raise RuntimeError("PID15184 current-parent calibration Construct did not pass")
        recovery_construct = json.loads((extracted / "PID4824_RECOVERY_IDENTITY_CONSTRUCT_RESULTS" / "report.json").read_text(encoding="utf-8"))
        floor_construct = json.loads((extracted / "PID4824_FLOOR_AUTHORITY_CONSTRUCT_RESULTS" / "report.json").read_text(encoding="utf-8"))
        if recovery_construct.get("passed") is not True or floor_construct.get("passed") is not True:
            raise RuntimeError("PID4824 recovery identity/floor authority Construct did not pass")
        sprout_construct = json.loads((extracted / "PID10656_SPROUT_HEIST_CONSTRUCT_RESULTS" / "report.json").read_text(encoding="utf-8"))
        patterns_construct = json.loads((extracted / "PID10656_LOOKING_GLASS_CONSTRUCT" / "construct_report.json").read_text(encoding="utf-8"))
        if sprout_construct.get("passed") is not True:
            raise RuntimeError("PID10656 fresh-sprout Heist Construct did not pass")
        if patterns_construct.get("passed") is not True or patterns_construct.get("javascript_passed") is not True:
            raise RuntimeError("PID10656 Looking Glass Python/actual-JavaScript Construct did not pass")
        validation = {
            "schema": "tachyos.opportunity_first.delivery_validation.v1", "release_id": RELEASE_ID,
            "status": "PASS", "created_at": datetime.now(timezone.utc).isoformat(),
            "environment": {"python": platform.python_version(), "platform": platform.platform()},
            "strategy_modified": True, "approved_corrections": APPROVED_CORRECTIONS,
            "recorded_source_run": "TOOL_RACK_PAPER_20261106T121055Z_PID3904",
            "recorded_source_zip_sha256": "ef711c357a903e0c39d20b2b9179d8c8b7aa00a2ba8febb8f89ed716261d78b6",
            "recorded_source_exact_replay_performed": False,
            "recorded_pid18244_trade6_positive_preserved": True,
            "recorded_strategy_test_module": "tests.tool_rack.test_opportunity_first_commander",
            "opportunity_first_sequence_audit": sequence_audit,
            "opportunity_first_engine_construct": engine_construct,
            "captured_baseline_archive_sha256": "ef711c357a903e0c39d20b2b9179d8c8b7aa00a2ba8febb8f89ed716261d78b6",
            "baseline_package_sha256": BASELINE_PACKAGE_SHA256,
            "sealed_strategy_config_ui_files": frozen_count, "approved_delta": approved_delta,
            "previous_package_sha256": PREVIOUS_PACKAGE_SHA256,
            "strategy_test_count": int(completed.group(1)), "strategy_test_module_count": len(TEST_MODULES),
            "capture_test_counts": capture_counts, "historical_abc_construct": construct,
            "recorded_rail_value_construct": rail_construct,
            "recorded_runtime_repair_construct": repair_construct,
            "recorded_late_scout_construct": scout_construct,
            "recorded_current_parent_calibration_construct": current_parent_construct,
            "recorded_recovery_identity_construct": recovery_construct,
            "recorded_floor_authority_construct": floor_construct,
            "recorded_fresh_sprout_heist_construct": sprout_construct,
            "looking_glass_patterns_construct": patterns_construct,
            "strategy_parameters_changed_by_this_repair": True,
            "three_way_synthetic_proof": proof, "check_transcript": checked_output,
            "three_way_strategy_modified_field_scope": "Synthetic recorder proves capture/replay integrity only. The separately recorded PID3904 chronological Commander comparison uses current-source evidence with causal watches and actual historical positive/negative controls. It does not recreate native Windows execution or establish alternate fills/profits.",
            "windows_runtime_verified": False, "real_market_counterfactual_replay": False,
            "profitability_proven": False, "six_hour_capture_accepted": False,
            "scope": "Opportunity-First shared positive admission, causal WAIT/PREPARE/ENTER watches, current EMA9 value joins, frozen local-return collection and parent-scale custody; all6,963 original decisions and all6,965 original calls in a fresh modified-engine Construct, historical Constructs, extracted-package tests, Windows launcher contracts, JavaScript and synthetic capture/replay integrity. Native Windows field behavior remains untested.",
        }
        # Prior validation records are historical audit records and remain
        # byte-for-byte unchanged. Finalize a NEW Opportunity-First
        # record only after all extracted strategy/capture/JS/replay gates pass.
        next_status = json.loads(payloads["NEXT_RUN_STATUS.json"])
        next_status.update({
            "release_id": RELEASE_ID,
            "previous_run": "TOOL_RACK_PAPER_20261106T121055Z_PID3904",
            "validation_record": "OPPORTUNITY_FIRST_VALIDATION.json",
            "ready_for_new_run": True,
            "release_validation": "RECORDED_SEQUENCE_ENGINE_CONSTRUCT_AND_EXTRACTED_FULL_DELIVERY_GATE_PASS",
            "stage": "VERIFIED_OPPORTUNITY_FIRST_COMMANDER_45M_PAPER_RELEASE",
            "windows_runtime_verified": False,
            "profitability_proven": False,
            "previous_recording_replayed": False,
            "modified_engine_construct_performed": True,
            "recorded_repair_effect": "Current-source Commander comparison passed all6,963 original decisions; the separate fresh modified-engine Construct passed all6,965 original calls and semantic controls. Prohibited source routes are withheld while independently qualified admissions, modeled custody and whole-lot exits remain exercised. No exact native replay or alternate-profit claim.",
        })
        final_evidence = {
            "OPPORTUNITY_FIRST_VALIDATION.json": validation,
            "NEXT_RUN_STATUS.json": next_status,
        }
        for name, item in final_evidence.items():
            payloads[name] = (json.dumps(item, indent=2, sort_keys=True) + "\n").encode("utf-8")
            manifest["files"][name] = {
                "sha256": hashlib.sha256(payloads[name]).hexdigest(),
                "size": len(payloads[name]),
            }
        payloads[MANIFEST_NAME] = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
        for name in (*final_evidence, MANIFEST_NAME):
            (extracted / name).write_bytes(payloads[name])
        # Only final release evidence/status and the manifest changed after
        # full tests. Every tested strategy, UI and launcher byte is identical.
        # Prove every final payload byte still matches the staged, tested package.
        for name, data in payloads.items():
            if (extracted / name).read_bytes() != data:
                raise RuntimeError("Payload changed during delivery checks: " + name)
        final_check = subprocess.run(
            [sys.executable, "-B", "CHECK_TOOL_RACK_PAPER.py", "--preflight-only", "--require-manifest"],
            cwd=extracted, env=environment, text=True, encoding="utf-8", stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, timeout=60, check=False)
        print(final_check.stdout, end="", flush=True)
        if final_check.returncode or "PREFLIGHT PASSED." not in final_check.stdout:
            raise RuntimeError("Final evidence/manifest integrity gate failed; no archive published")
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name, data in sorted(payloads.items()):
                archive.writestr(name, data)
        with zipfile.ZipFile(archive_path, "r") as archive:
            if len(archive.namelist()) != len(payloads) or set(archive.namelist()) != set(payloads):
                raise RuntimeError("Final archive whitelist mismatch")
            for name, data in payloads.items():
                if archive.read(name) != data:
                    raise RuntimeError("Final archive byte verification failed: " + name)
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
        "payload_file_count": len(PACKAGE_FILES),
        "zip_member_count": len(PACKAGE_FILES) + 1,
        "manifest": MANIFEST_NAME,
        "zip_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "extracted_check": "PASSED",
        "verified_with_python": sys.version.split()[0],
        "mode": "PAPER",
        "venue_order_authority": "NONE",
        "engineering_candidate": False,
        "sealed_strategy_config_ui_files": frozen_count,
        "strategy_test_count": int(completed.group(1)),
        "capture_test_counts": capture_counts,
        "strategy_modified": True,
        "approved_corrections": APPROVED_CORRECTIONS,
        "three_way_synthetic_proof": "PASS",
        "windows_runtime_verified": False,
        "six_hour_capture_accepted": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--capture-candidate", action="store_true",
                        help="Retained for explicit rejection: this corrected strategy requires every delivery gate.")
    args = parser.parse_args(argv)
    try:
        output = args.output or Path("TACHYOS_OPPORTUNITY_FIRST_COMMANDER_45M_PAPER_20261106.zip")
        result = build(args.root, output, capture_candidate=args.capture_candidate)
    except Exception as exc:
        print(f"BUILD FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
