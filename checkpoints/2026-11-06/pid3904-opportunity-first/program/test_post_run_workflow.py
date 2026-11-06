"""Complete evidence, independent Windows display, and exact small-upload binding."""
from __future__ import annotations

from contextlib import redirect_stdout
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import zipfile

import complete_paper_run as completion
import post_run_monitor as monitor
from test_complete_paper_run import fake_closed_capture


class OriginalEvidenceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="tachyos_complete_upload_")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.run, self.program = fake_closed_capture(self.root)
        self.output = self.root / "PAPER_RESULTS"
        self.stream = io.StringIO()

    def complete(self, **kwargs):
        return completion.complete_run(self.run, program_root=self.program,
            output_dir=self.output, lease_path=self.root / "global.lock", stream=self.stream, **kwargs)

    def test_normal_btc_source_log_survives_complete_export_and_lossless_parts(self):
        raw = gzip.compress(b'{"kind":"PUBLIC_FRAME","raw":"exact fixture bytes"}\r\n')
        (self.run / "btc_public_source.jsonl.gz").write_bytes(raw)
        pointer = self.root / "pointer.json"
        status = self.complete(small_uploads=True, status_pointer=pointer)
        self.assertEqual(completion.result_code(status), 0, status)
        self.assertEqual(status["replay"]["state"], "NOT_REQUESTED")
        restored = bytearray()
        for name in status["uploads"]["parts"]:
            with zipfile.ZipFile(name) as part:
                restored.extend(part.read("archive_chunk.bin"))
        archive = Path(status["export"]["archive"])
        self.assertEqual(bytes(restored), archive.read_bytes())
        with zipfile.ZipFile(archive) as saved:
            self.assertEqual(saved.read("original/" + self.run.name + "/btc_public_source.jsonl.gz"), raw)
            report = json.loads(saved.read("COMPLETION_REPORT.json"))
            self.assertNotIn("btc_public_source.jsonl.gz", report["engine_inventory"]["files"])
        validated, _, complete = monitor.validate_completion(pointer, self.run, self.output)
        self.assertTrue(complete)
        self.assertEqual(validated["binding"]["archive_sha256"], status["uploads"]["source_sha256"])
        self.assertEqual((self.run / "btc_public_source.jsonl.gz").read_bytes(), raw)

    def test_unknown_file_writes_terminal_error_instead_of_staying_at_starting(self):
        (self.run / "unexpected_persistent_file.bin").write_bytes(b"must not be omitted")
        with self.assertRaisesRegex(completion.CompletionError, "UNDECLARED_RUN_FILE"):
            self.complete()
        path, = self.output.glob("*/POST_RUN_STATUS.json")
        status = json.loads(path.read_bytes())
        self.assertEqual(status["export"]["state"], "ERROR")
        self.assertEqual(status["progress"]["phase"], "Completion failed")
        self.assertIn("unexpected_persistent_file.bin", status["export"]["failure"]["message"])
        self.assertFalse(list(self.output.glob("*.zip")))

    def test_new_persistent_file_appearing_during_verification_prevents_publication(self):
        verify = completion._verify_archive
        def change_then_verify(*args, **kwargs):
            result = verify(*args, **kwargs)
            (self.run / "btc_public_source.jsonl.gz").write_bytes(gzip.compress(b"late file"))
            return result
        with patch.object(completion, "_verify_archive", side_effect=change_then_verify):
            with self.assertRaisesRegex(completion.CompletionError, "SOURCE_FILE_SET_CHANGED"):
                self.complete()
        self.assertFalse(list(self.output.glob("*.zip")))

    def test_upload_failure_retains_complete_archive_and_returns_failure(self):
        import make_upload_parts
        with patch.object(make_upload_parts, "verify_parts", side_effect=OSError("injected part failure")):
            with self.assertRaisesRegex(completion.CompletionError, "SMALL_UPLOADS_FAILED"):
                self.complete(small_uploads=True)
        path, = self.output.glob("*/POST_RUN_STATUS.json")
        status = json.loads(path.read_bytes())
        self.assertEqual(status["export"]["state"], "VERIFIED")
        self.assertEqual(status["uploads"]["state"], "ERROR")
        self.assertEqual(completion.result_code(status), 1)
        self.assertTrue(Path(status["export"]["archive"]).is_file())

    def test_status_pointer_cannot_modify_the_original_or_captured_program(self):
        for protected in (self.run, self.program):
            with self.subTest(protected=protected):
                with self.assertRaisesRegex(completion.CompletionError, "STATUS_POINTER_MUST_BE_OUTSIDE"):
                    self.complete(status_pointer=protected / "pointer.json")
                self.assertFalse((protected / "pointer.json").exists())

    def test_monitor_rejects_uploads_bound_to_another_archive(self):
        pointer = self.root / "pointer.json"
        status = self.complete(small_uploads=True, status_pointer=pointer)
        status["uploads"]["source_sha256"] = "f" * 64
        Path(status["status_path"]).write_text(json.dumps(status), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "do not match"):
            monitor.validate_completion(pointer, self.run, self.output)


class DisplayIsolationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="tachyos_completion_display_")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def test_worker_completes_while_first_console_write_is_blocked(self):
        entered, release = threading.Event(), threading.Event()
        class BlockedViewer(io.StringIO):
            def write(self, text):
                entered.set()
                if not release.wait(10):
                    raise RuntimeError("viewer control timeout")
                return super().write(text)
        finished = self.root / "worker_finished.txt"
        script = "import pathlib,sys; print('progress',flush=True); pathlib.Path(sys.argv[1]).write_bytes(b'complete')"
        child, result, errors = [], [], []
        def run():
            try:
                result.append(monitor.execute_logged([sys.executable, "-c", script, str(finished)],
                    self.root / "log.txt", stream=BlockedViewer(), on_started=child.append))
            except BaseException as exc:
                errors.append(exc)
        viewer = threading.Thread(target=run)
        viewer.start()
        try:
            self.assertTrue(entered.wait(5))
            self.assertEqual(child[0].wait(timeout=5), 0)
            self.assertEqual(finished.read_bytes(), b"complete")
            self.assertTrue(viewer.is_alive())
        finally:
            release.set()
            viewer.join(timeout=5)
        self.assertEqual(errors, [])
        self.assertEqual(result, [0])

    def test_exact_worker_exit_code_is_preserved(self):
        code = monitor.execute_logged([sys.executable, "-c", "raise SystemExit(17)"],
            self.root / "log.txt", stream=io.StringIO())
        self.assertEqual(code, 17)

    def test_zero_worker_exit_without_verified_status_is_failure(self):
        run = self.root / "NEW_RUN"
        run.mkdir()
        with patch.object(monitor, "execute_logged", return_value=0):
            code = monitor.run_completion(run, output_dir=self.root / "results", stream=io.StringIO())
        self.assertEqual(code, 1)

    def test_missing_receipt_never_selects_or_exports_previous_run(self):
        with patch.object(monitor, "run_completion") as complete, redirect_stdout(io.StringIO()):
            code = monitor.main(["--run-receipt", str(self.root / "missing.json")])
        self.assertEqual(code, 1)
        complete.assert_not_called()

    def test_windows_child_is_separate_from_console_and_receives_exact_paths(self):
        with patch.object(monitor.os, "name", "nt"), patch.object(subprocess, "CREATE_NO_WINDOW", 0x08000000, create=True):
            self.assertEqual(monitor._process_options(), {"creationflags": 0x08000000})
        command = monitor._command(self.root, self.root / "exact_run", self.root / "results", self.root / "pointer.json")
        self.assertEqual(command[command.index("--run") + 1], str(self.root / "exact_run"))
        self.assertIn("--small-uploads", command)
        self.assertNotIn("--replay", command)


class RealClosedCaptureWorkflowTests(unittest.TestCase):
    def test_actual_raw_feed_producer_to_file_backed_worker_and_small_uploads(self):
        """Runs on the sealed extracted package; no market connection is opened."""
        from capture_session import finish_capture
        from engine_replay import RecordedEngine, ScriptClock
        from strategy_core.marketdata.btc_transport import PublicFeed
        def denied(*args, **kwargs):
            raise AssertionError("OFFLINE_PRODUCER_NETWORK_FORBIDDEN")
        with tempfile.TemporaryDirectory(prefix="tachyos_closed_full_workflow_") as temporary:
            root = Path(temporary)
            run = root / "ACTUAL_PRODUCER_CLOSED_CAPTURE"
            stream = io.StringIO()
            with patch.object(socket.socket, "connect", side_effect=denied), \
                 patch.object(socket, "create_connection", side_effect=denied), \
                 patch.object(socket, "getaddrinfo", side_effect=denied):
                recorder = RecordedEngine(run, run / completion.TAPE_NAME,
                    input_kind="SYNTHETIC_CLOSED_PUBLIC_FEED_PRODUCER",
                    clock_supplier=ScriptClock(1800000000.0))
                feed = PublicFeed(run, seed_fetch=denied, connect=denied)
                record = {"kind": "PUBLIC_FRAME", "epoch": 1, "received_wall": 1800000000.123456,
                          "raw": "synthetic offline transport record"}
                async def local_run():
                    feed._record(record)
                with patch.object(feed, "_run", side_effect=local_run):
                    feed._main()
                self.assertIsNone(feed.error)
                raw = (run / "btc_public_source.jsonl.gz").read_bytes()
                self.assertEqual(json.loads(gzip.decompress(raw)), record)
                recorder.close(reason="SYNTHETIC_CLOSED", clock_supplier=ScriptClock(1800000001.0))
                with redirect_stdout(stream):
                    health = finish_capture(recorder, reason="SYNTHETIC_CLOSED")
                self.assertTrue(health["replay_ready"], health)
                before = {p.relative_to(run).as_posix(): p.read_bytes() for p in run.rglob("*")
                          if p.is_file() and p.name != "paper_writer.lock"}
                code = monitor.run_completion(run, output_dir=root / "results", stream=stream, open_folder=False)
            self.assertEqual(code, 0, stream.getvalue())
            pointer, = (root / "results").glob("*_COMPLETION_LAUNCH_*/STATUS_POINTER.json")
            status, _, complete = monitor.validate_completion(pointer, run, root / "results")
            self.assertTrue(complete)
            archive = Path(status["export"]["archive"])
            self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(), status["uploads"]["source_sha256"])
            with zipfile.ZipFile(archive) as saved:
                for name, data in before.items():
                    self.assertEqual(saved.read("original/" + run.name + "/" + name), data, name)
                    self.assertEqual((run / name).read_bytes(), data, name)
                manifest = json.loads((completion.ROOT / completion.BUNDLE_NAME).read_bytes())
                for name in [*manifest["files"], completion.BUNDLE_NAME]:
                    self.assertEqual(saved.read("program/" + name), (completion.ROOT / name).read_bytes(), name)
            self.assertEqual(status["replay"]["state"], "NOT_REQUESTED")


if __name__ == "__main__":
    unittest.main()
