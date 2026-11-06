"""Focused checks for recording lifecycle and the declared live output scope."""
from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bounded_tape import TapeError, iter_tape
from capture_session import (CAPTURE_DIRECTORY, STATUS_NAME, TAPE_NAME,
                             engine_output_inventory, finish_capture, verify_engine_inventory)
from engine_replay import (RecordedEngine, ScriptClock, compare_directories,
                           replay, require_fresh)


class CaptureSessionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="tachyos_capture_session_")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def closed_capture(self, name="RUN"):
        run = self.root / name
        run.mkdir()
        (run / "console.log").write_text("Launcher-owned supporting output.\n", encoding="utf-8")
        recorder = RecordedEngine(run, run / CAPTURE_DIRECTORY / TAPE_NAME,
            input_kind="SYNTHETIC_CAPTURE_SESSION_INTEGRATION", clock_supplier=ScriptClock(1800000000.0),
            allowed_launcher_files=("console.log",))
        # Use the original adapter close, with deterministic fixture time,
        # and then the reporting path. Idempotence means no second engine close.
        recorder.close(reason="SYNTHETIC_CLOSED", clock_supplier=ScriptClock(1800000001.0))
        with redirect_stdout(io.StringIO()):
            health = finish_capture(recorder, reason="SYNTHETIC_CLOSED")
        self.assertTrue(health["replay_ready"], health)
        return run, recorder, health

    def test_console_exception_never_permits_prior_engine_state(self):
        run = self.root / "FRESH"
        run.mkdir()
        (run / "console.log").write_text("", encoding="utf-8")
        require_fresh(run, allowed_launcher_files=("console.log",))
        (run / "PAPER_LEDGER.json").write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(TapeError, "FRESH_EMPTY"):
            require_fresh(run, allowed_launcher_files=("console.log",))
        with self.assertRaisesRegex(TapeError, "UNSUPPORTED_FRESH"):
            require_fresh(run, allowed_launcher_files=("PAPER_LEDGER.json",))

    def test_close_once_and_complete_live_output_scope(self):
        run, recorder, health = self.closed_capture()
        first_manifest = recorder.close(reason="IGNORED_SECOND_CLOSE")
        self.assertEqual(first_manifest["written"], 2)
        self.assertEqual(finish_capture(recorder, reason="IGNORED"), health)
        _, calls = iter_tape(run / CAPTURE_DIRECTORY / TAPE_NAME)
        self.assertEqual([call["call"]["method"] for call in calls], ["init", "close"])
        inventory = verify_engine_inventory(run)
        self.assertNotIn("console.log", inventory["files"])
        with redirect_stdout(io.StringIO()):
            result = replay(run / CAPTURE_DIRECTORY / TAPE_NAME, self.root / "replayed",
                reference_dir=run, reference_files=tuple(inventory["files"]))
        self.assertTrue(result["pass"])
        self.assertEqual(result["files_compared"], 9)
        replay_dir = Path(result["run_dir"])
        (replay_dir / "unexpected.json").write_text("{}", encoding="utf-8")
        compared = compare_directories(run, replay_dir, reference_files=tuple(inventory["files"]))
        self.assertFalse(compared["pass"])
        self.assertEqual(compared["differences"][0]["file"], "unexpected.json")

    def test_inventory_rejects_modified_or_missing_original_output(self):
        run, _, _ = self.closed_capture()
        ledger = run / "PAPER_LEDGER.json"
        ledger.write_bytes(ledger.read_bytes() + b" ")
        with self.assertRaisesRegex(TapeError, "OUTPUTS_CHANGED"):
            verify_engine_inventory(run)
        ledger.unlink()
        with self.assertRaisesRegex(TapeError, "MISSING_ENGINE_OUTPUTS"):
            engine_output_inventory(run)

    def test_reporting_failure_cannot_claim_replay_ready(self):
        run = self.root / "FAILED_SIDECAR"
        recorder = RecordedEngine(run, run / CAPTURE_DIRECTORY / TAPE_NAME,
            input_kind="SYNTHETIC_FAILED_SIDECAR", clock_supplier=ScriptClock(1800000000.0))
        recorder.close(reason="SYNTHETIC_CLOSED", clock_supplier=ScriptClock(1800000001.0))
        with patch("capture_session.write_json", side_effect=OSError("injected disk failure")), redirect_stdout(io.StringIO()):
            health = finish_capture(recorder, reason="SYNTHETIC_CLOSED")
        self.assertFalse(health["replay_ready"])
        self.assertTrue(health["engine_closed"])
        self.assertFalse((run / STATUS_NAME).exists())


if __name__ == "__main__":
    unittest.main()
