"""Export-first completion, independent archive checks and tiny exact replay.

The synthetic integration fixture records only construction and close. It does
not start a market feed, run a 45-minute session, or reuse old recorded results.
"""
from __future__ import annotations

import builtins
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import platform
import tempfile
import time
import unittest
from unittest.mock import patch
import zipfile

import complete_paper_run as completion


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def fake_closed_capture(root):
    """Authored metadata sufficient for export; never offered as replay PASS."""
    program = root / "program"
    program.mkdir()
    files = {name: ("# Fixture " + name + "\n").encode() for name in completion.RECORDER_NAMES}
    files["complete_paper_run.py"] = b"# Independent fixture export program\n"
    files["strategy_core/core.py"] = b"# Frozen fixture core\n"
    source = {"strategy_core/core.py": digest(files["strategy_core/core.py"])}
    files["SOURCE_SHA256.json"] = (json.dumps(source) + "\n").encode()
    for name, data in files.items():
        path = program / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    write_json(program / completion.BUNDLE_NAME, {
        "schema": "TACHYOS_TOOL_RACK_PAPER_BUNDLE_V1", "mode": "PAPER",
        "venue_order_authority": "NONE", "release_id": "SYNTHETIC_EXPORT_TEST_ONLY",
        "files": {name: {"size": len(data), "sha256": digest(data)} for name, data in files.items()},
    })
    files[completion.BUNDLE_NAME] = (program / completion.BUNDLE_NAME).read_bytes()
    source_files = {name: digest(data) for name, data in files.items()}
    run = root / "RUN_A"
    run.mkdir()
    for name in completion.ENGINE_NAMES:
        (run / name).write_bytes(b'{"decision":"WAIT","clock":1800000000.0000123}\r\n')
    write_json(run / "RUN_MANIFEST.json", {
        "run_id": run.name, "mode": "PAPER", "files": source_files,
        "source_and_config_sha256": digest(json.dumps(source_files, sort_keys=True, separators=(",", ":")).encode()),
    })
    write_json(run / "RUN_SUMMARY.json", {"mode": "PAPER", "run_id": run.name,
        "state": "STOPPED", "cash": 1000.0, "unresolved_inventory_count": 0,
        "sequence": 0, "stop_reason": "SYNTHETIC_CLOSED"})
    write_json(run / "STATUS.json", {"state": "STOPPED"})
    write_json(run / "paper_journal/00000001.json", {"fixture": "committed"})
    (run / "console.log").write_bytes(b"Original console: do not rewrite.\r\n")
    header = {"schema": "tachyos.engine_input_tape.v2", "kind": "HEADER", "sequence": 0,
        "previous_sha256": "0" * 64, "payload": {"run_id": run.name,
            "source_hashes": source, "recorder_source_hashes": {name: digest(files[name]) for name in completion.RECORDER_NAMES},
            "python": platform.python_version(), "implementation": platform.python_implementation(),
            "initial_state": "FRESH_CONSTRUCTOR_NO_RESTORED_INVENTORY"}}
    header["sha256"] = digest(json.dumps(header, sort_keys=True, separators=(",", ":"),
                                        ensure_ascii=True, allow_nan=False).encode())
    tape = (json.dumps(header) + "\n" + '{"fixture":"not a replay proof"}\n').encode()
    (run / "replay_capture").mkdir()
    (run / completion.TAPE_NAME).write_bytes(tape)
    counts = {"complete": True, "attempted": 2, "accepted": 2, "written": 2,
              "dropped": 0, "bytes": len(tape), "reason": None, "writer_alive": False}
    write_json(run / completion.TAPE_MANIFEST, {**counts,
        "schema": "tachyos.engine_input_tape_manifest.v2", "tape_schema": "tachyos.engine_input_tape.v2",
        "header_sha256": header["sha256"]})
    write_json(run / "CAPTURE_STATUS.json", {**counts, "engine_closed": True,
        "replay_ready": True, "engine_output_inventory_complete": True})
    engine_names = list(completion.ENGINE_NAMES) + ["paper_journal/00000001.json"]
    write_json(run / "ENGINE_OUTPUTS.json", {
        "schema": "tachyos.closed_engine_outputs.v1", "run_id": run.name,
        "files": {name: {"bytes": len((run / name).read_bytes()), "sha256": digest((run / name).read_bytes())}
                  for name in engine_names},
    })
    return run, program


class CompletionExportTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="tachyos_completion_")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.run, self.program = fake_closed_capture(self.root)
        self.output = self.root / "results"
        self.stream = io.StringIO()
        self.lease = self.root / "global.lock"

    def complete(self, **kwargs):
        return completion.complete_run(self.run, output_dir=self.output, program_root=self.program,
            lease_path=self.lease, stream=self.stream, **kwargs)

    def test_default_export_preserves_every_byte_and_never_imports_engine(self):
        originals = {path.relative_to(self.run).as_posix(): path.read_bytes()
                     for path in self.run.rglob("*") if path.is_file()}
        original_import = builtins.__import__

        def no_engine_import(name, *args, **kwargs):
            self.assertFalse(name == "engine_replay" or name.startswith("strategy_core"), name)
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=no_engine_import):
            status = self.complete()
        self.assertEqual(completion.result_code(status), 0)
        self.assertEqual(status["capture"]["state"], "REPORTED_COMPLETE")
        self.assertEqual(status["export"]["state"], "VERIFIED")
        self.assertEqual(status["replay"]["state"], "NOT_REQUESTED")
        archive_path = Path(status["export"]["archive"])
        self.assertEqual(digest(archive_path.read_bytes()), status["export"]["sha256"])
        with zipfile.ZipFile(archive_path) as archive:
            report = json.loads(archive.read(completion.REPORT_NAME))
            self.assertEqual(report["export"]["source_files"], len(originals))
            self.assertEqual(report["replay"], {"state": "NOT_REQUESTED", "performed": False})
            self.assertEqual(report["program"]["state"], "MATCHED_CAPTURE")
            self.assertTrue(report["inventory_matches"])
            self.assertFalse(any(name.startswith("replay/") for name in archive.namelist()))
            for name, data in originals.items():
                archived = archive.read("original/" + self.run.name + "/" + name)
                self.assertEqual(archived, data, name)
                self.assertEqual((self.run / name).read_bytes(), data, name)
            for name, record in report["files"].items():
                data = archive.read(name)
                self.assertEqual(record, {"bytes": len(data), "sha256": digest(data)})
            self.assertIn("program/complete_paper_run.py", archive.namelist())
        self.assertIn("COMPLETE ORIGINAL ZIP: " + str(archive_path), self.stream.getvalue())
        self.assertEqual(json.loads(Path(status["status_path"]).read_text(encoding="utf-8"))["replay"]["state"], "NOT_REQUESTED")
        self.assertFalse(list(self.output.glob("*.partial")))

    def test_unique_exports_never_replace_an_existing_archive(self):
        first = self.complete()
        archive = Path(first["export"]["archive"])
        initial = archive.read_bytes()
        second = self.complete()
        self.assertNotEqual(first["export"]["archive"], second["export"]["archive"])
        self.assertEqual(archive.read_bytes(), initial)
        temporary = self.output / "another.partial"
        temporary.write_bytes(b"must not overwrite")
        with self.assertRaises(FileExistsError):
            completion._publish_unique(temporary, archive)
        self.assertEqual(archive.read_bytes(), initial)

    def test_program_mismatch_still_saves_diagnostic_original_without_pass(self):
        (self.program / "strategy_core/core.py").write_text("# changed\n", encoding="utf-8")
        status = self.complete()
        self.assertEqual(status["export"]["state"], "VERIFIED")
        self.assertEqual(status["program"]["state"], "NOT_MATCHED")
        self.assertEqual(status["replay"]["state"], "NOT_REQUESTED")
        self.assertEqual(completion.result_code(status), 2)
        with zipfile.ZipFile(status["export"]["archive"]) as archive:
            self.assertTrue(any(name.startswith("original/") for name in archive.namelist()))
            self.assertFalse(any(name.startswith("program/") for name in archive.namelist()))

    def test_original_output_mismatch_is_diagnostic_not_capture_or_replay_pass(self):
        ledger = self.run / "PAPER_LEDGER.json"
        changed = ledger.read_bytes() + b" "
        ledger.write_bytes(changed)
        status = self.complete()
        self.assertEqual(status["capture"]["state"], "ORIGINAL_OUTPUTS_CHANGED")
        self.assertFalse(status["export"]["inventory_matches"])
        self.assertEqual(completion.result_code(status), 2)
        with zipfile.ZipFile(status["export"]["archive"]) as archive:
            self.assertEqual(archive.read("original/RUN_A/PAPER_LEDGER.json"), changed)

    def test_incomplete_manifest_counts_cannot_claim_complete_capture(self):
        path = self.run / completion.TAPE_MANIFEST
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["written"] = 1
        write_json(path, manifest)
        status = self.complete()
        self.assertEqual(status["capture"]["state"], "REPORTED_INCOMPLETE")
        self.assertEqual(status["export"]["state"], "VERIFIED")
        self.assertEqual(completion.result_code(status), 2)

    def test_rejects_active_global_lease_and_unclosed_run(self):
        with completion.exclusive_completion_lease(self.lease):
            with self.assertRaisesRegex(completion.CompletionError, "ANOTHER_TOOL_RACK"):
                self.complete()
        self.assertFalse(self.output.exists())
        summary = json.loads((self.run / "RUN_SUMMARY.json").read_text(encoding="utf-8"))
        summary["state"] = "RUNNING"
        write_json(self.run / "RUN_SUMMARY.json", summary)
        with self.assertRaisesRegex(completion.CompletionError, "NOT_CLOSED"):
            self.complete()
        self.assertFalse(list(self.output.glob("*.zip")))

    def test_verification_failure_leaves_no_published_or_partial_zip(self):
        with patch.object(completion, "_verify_archive", side_effect=OSError("injected verification failure")):
            with self.assertRaisesRegex(OSError, "injected verification failure"):
                self.complete()
        self.assertFalse(list(self.output.glob("*.zip")))
        self.assertFalse(list(self.output.glob("*.partial")))
        status_file, = self.output.glob("*/POST_RUN_STATUS.json")
        status = json.loads(status_file.read_text(encoding="utf-8"))
        self.assertEqual(status["export"]["state"], "ERROR")
        self.assertEqual(status["replay"]["state"], "NOT_REQUESTED")

    def test_heartbeat_failure_after_publication_retains_and_prints_archive_path(self):
        published = []
        publish = completion._publish_unique
        check = completion.Progress.check

        def publish_then_fail(temporary, destination):
            publish(temporary, destination)
            published.append(destination)

        def failed_check(progress):
            if published:
                raise completion.CompletionError("injected heartbeat failure after publication")
            return check(progress)

        with patch.object(completion, "_publish_unique", side_effect=publish_then_fail), \
             patch.object(completion.Progress, "check", autospec=True, side_effect=failed_check):
            with self.assertRaisesRegex(completion.CompletionError, "after publication"):
                self.complete()
        archive, = published
        self.assertTrue(archive.is_file())
        self.assertIn("COMPLETE ORIGINAL ZIP: " + str(archive), self.stream.getvalue())
        status_file, = self.output.glob("*/POST_RUN_STATUS.json")
        status = json.loads(status_file.read_text(encoding="utf-8"))
        self.assertEqual(status["export"]["state"], "VERIFIED")
        self.assertEqual(status["export"]["archive"], str(archive))
        self.assertEqual(status["replay"]["state"], "NOT_REQUESTED")
        self.assertEqual(status["completion_error"]["state"], "ERROR")

    def test_heartbeat_failure_cannot_leave_terminal_replay_report_running(self):
        for exception, expected in ((RuntimeError("worker stopped"), "ERROR"),
                                     (KeyboardInterrupt(), "INTERRUPTED")):
            observed = []

            def fail_worker(reference, replay_parent, progress, **kwargs):
                observed.append(progress.status)
                progress.failure = OSError("injected heartbeat write failure")
                raise exception

            with self.subTest(expected=expected), \
                 patch.object(completion, "_perform_replay", side_effect=fail_worker):
                with self.assertRaisesRegex(completion.CompletionError, "PROGRESS_STATUS_WRITE_FAILED"):
                    self.complete(replay_requested=True)
            status, = observed
            work = Path(status["status_path"]).parent
            result = json.loads((work / "REPLAY_RESULT.json").read_text(encoding="utf-8"))
            saved = json.loads((work / completion.STATUS_NAME).read_text(encoding="utf-8"))
            self.assertEqual(result["replay"]["state"], expected)
            self.assertEqual(saved["replay"]["state"], expected)
            self.assertFalse(result["pass"])
            self.assertTrue(Path(saved["export"]["archive"]).is_file())

    def test_replay_start_heartbeat_failure_still_writes_terminal_result(self):
        exported = self.complete()
        archive = Path(exported["export"]["archive"])
        work, _, status = completion._new_status(self.run.name, archive, self.output, replay_requested=True)
        with completion.Progress(work / completion.STATUS_NAME, status, stream=self.stream) as progress:
            progress.failure = OSError("injected pre-existing heartbeat failure")
            completion.replay_published_archive(archive, work, status, progress, program_root=self.program)
        result = json.loads((work / "REPLAY_RESULT.json").read_text(encoding="utf-8"))
        self.assertEqual(result["replay"]["state"], "ERROR")
        self.assertFalse(result["pass"])
        self.assertIn("PROGRESS_STATUS_WRITE_FAILED", result["replay"]["failure"]["message"])

    def test_explicit_replay_starts_after_verified_archive_and_interrupt_keeps_it(self):
        def interrupted(reference, replay_parent, progress, **kwargs):
            self.assertTrue(Path(progress.status["export"]["archive"]).is_file())
            self.assertEqual(progress.status["export"]["state"], "VERIFIED")
            self.assertNotEqual(reference, self.run)
            self.assertEqual((reference / completion.TAPE_NAME).read_bytes(), (self.run / completion.TAPE_NAME).read_bytes())
            raise KeyboardInterrupt()

        with patch.object(completion, "_perform_replay", side_effect=interrupted) as replay:
            status = self.complete(replay_requested=True)
        replay.assert_called_once()
        self.assertEqual(status["replay"]["state"], "INTERRUPTED")
        self.assertEqual(completion.result_code(status), 130)
        self.assertTrue(Path(status["export"]["archive"]).is_file())
        result = json.loads((Path(status["status_path"]).parent / "REPLAY_RESULT.json").read_text(encoding="utf-8"))
        self.assertFalse(result["pass"])
        self.assertEqual(result["binding"]["archive_sha256"], status["export"]["sha256"])
        with zipfile.ZipFile(status["export"]["archive"]) as archive:
            self.assertEqual(json.loads(archive.read(completion.REPORT_NAME))["replay"]["state"], "NOT_REQUESTED")

    def test_changed_archived_bytes_fail_before_replay(self):
        status = self.complete()
        source = Path(status["export"]["archive"])
        changed = self.root / "changed.zip"
        with zipfile.ZipFile(source) as original, zipfile.ZipFile(changed, "w") as output:
            for name in original.namelist():
                data = original.read(name)
                if name.endswith("/decisions.jsonl"):
                    data += b" "
                output.writestr(name, data)
        with patch.object(completion, "_perform_replay") as replay:
            result = completion.replay_archive(changed, output_dir=self.output, program_root=self.program,
                lease_path=self.lease, stream=self.stream)
        replay.assert_not_called()
        self.assertEqual(result["replay"]["state"], "ERROR")
        self.assertIn("ARCHIVED_BYTES_DIFFER", result["replay"]["failure"]["message"])
        self.assertTrue(source.is_file())

    def test_missing_receipt_never_selects_a_previous_run(self):
        with patch.object(completion, "complete_run") as complete, redirect_stdout(self.stream):
            code = completion.main(["--run-receipt", str(self.root / "missing.json")])
        self.assertEqual(code, 1)
        complete.assert_not_called()

    def test_heartbeat_continues_during_a_slow_phase(self):
        path = self.root / "heartbeat.json"
        status = {"capture": {}, "export": {}, "replay": {}}
        with completion.Progress(path, status, interval=0.01, stream=self.stream) as progress:
            progress.phase("Compressing complete recording", total=100)
            time.sleep(0.075)
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertGreater(saved["elapsed_seconds"], 0.02)
            self.assertEqual(saved["progress"]["phase"], "Compressing complete recording")
        self.assertGreaterEqual(self.stream.getvalue().count("Compressing complete recording"), 3)
        self.assertLessEqual(completion.HEARTBEAT_SECONDS, 5)


class CompletionRecordedIntegrationTests(unittest.TestCase):
    """Requires the current package manifest to be sealed before it runs."""
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="tachyos_completion_recorded_")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.stream = io.StringIO()

    def recorded(self):
        from capture_session import finish_capture
        from engine_replay import RecordedEngine, ScriptClock
        run = self.root / "TINY_RECORDED_RUN"
        recorder = RecordedEngine(run, run / completion.TAPE_NAME,
            input_kind="SYNTHETIC_COMPLETION_CONSTRUCTION_AND_CLOSE",
            clock_supplier=ScriptClock(1800000000.0))
        recorder.close(reason="SYNTHETIC_CLOSED", clock_supplier=ScriptClock(1800000001.0))
        with redirect_stdout(self.stream):
            health = finish_capture(recorder, reason="SYNTHETIC_CLOSED")
        self.assertTrue(health["replay_ready"], health)
        return run

    def test_actual_exact_replay_uses_one_tape_validation_and_all_outputs(self):
        import engine_replay
        run = self.recorded()
        with patch.object(engine_replay, "replay", wraps=engine_replay.replay) as replay, \
             patch.object(engine_replay, "iter_tape", wraps=engine_replay.iter_tape) as validate, \
             patch("finish_recorded_run._recording_header", side_effect=AssertionError("legacy full pass forbidden")):
            status = completion.complete_run(run, output_dir=self.root / "results", replay_requested=True,
                lease_path=self.root / "global.lock", stream=self.stream)
        self.assertEqual(status["replay"]["state"], "PASS", status)
        self.assertEqual(completion.result_code(status), 0)
        replay.assert_called_once()
        validate.assert_called_once()
        result = status["replay"]["result"]
        inventory = json.loads((run / "ENGINE_OUTPUTS.json").read_text(encoding="utf-8"))
        self.assertEqual(result["calls"], 2)
        self.assertEqual(result["files_compared"], len(inventory["files"]))
        self.assertEqual(result["validation_scope"], "ALL_PERSISTENT_ENGINE_OUTPUT_FILES")
        self.assertNotEqual(Path(result["run_dir"]), run)

    def test_bad_final_tape_record_cannot_construct_replay_engine(self):
        import engine_replay
        run = self.recorded()
        tape = run / completion.TAPE_NAME
        original = tape.read_bytes()
        # Same byte count and intact header; the verified spool must reject the
        # corrupt END record before constructing even one replay engine.
        position = original.rfind(b'"sha256":"')
        self.assertGreater(position, 0)
        position += len(b'"sha256":"')
        changed = original[:position] + (b"0" if original[position:position + 1] != b"0" else b"1") + original[position + 1:]
        tape.write_bytes(changed)
        with patch.object(engine_replay.runtime, "ToolRackPaperEngine") as engine:
            status = completion.complete_run(run, output_dir=self.root / "results", replay_requested=True,
                lease_path=self.root / "global.lock", stream=self.stream)
        engine.assert_not_called()
        self.assertEqual(status["export"]["state"], "VERIFIED")
        self.assertEqual(status["replay"]["state"], "FAIL", status)
        self.assertFalse(json.loads((Path(status["status_path"]).parent / "REPLAY_RESULT.json").read_text(encoding="utf-8"))["pass"])


class CompletionWindowsEntrypointTests(unittest.TestCase):
    def test_main_preserves_preflight_receipt_and_makes_replay_explicit(self):
        text = (completion.ROOT / "00_PREPARE_AND_RUN_45M_PAPER.cmd").read_text(encoding="utf-8")
        self.assertIn("setlocal DisableDelayedExpansion", text)
        preflight = text.index("--preflight-only --require-manifest")
        prepare = text.index('"%TR_ROOT%prepare_next_run.py"\n')
        start = text.index("--minutes 45 --record-for-replay --run-receipt")
        export = text.index('"%TR_ROOT%post_run_monitor.py" --run-receipt')
        self.assertLess(preflight, prepare)
        self.assertLess(prepare, start)
        self.assertLess(start, export)
        self.assertIn('if not exist "%TR_RECEIPT%" goto no_new_run', text)
        self.assertNotIn('"%TR_ROOT%finish_recorded_run.py" --run-receipt', text)
        self.assertNotIn('"%TR_ROOT%post_run_monitor.py" --run-receipt "%TR_RECEIPT%" --replay', text)
        optional = (completion.ROOT / "07_REPLAY_CLOSED_PAPER_RUN.cmd").read_text(encoding="utf-8")
        self.assertIn('--archive "%TR_ARCHIVE%" --replay', optional)
        self.assertNotIn("LAST_RUN", optional)


if __name__ == "__main__":
    unittest.main()
