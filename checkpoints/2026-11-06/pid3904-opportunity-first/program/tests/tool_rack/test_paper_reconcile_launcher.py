"""Stopped-run repair through real journals and exact public-receipt parsing."""
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import TOOL_RACK_RECONCILE as repair
import TOOL_RACK_PAPER as launch
from TOOL_RACK_EXPORT import export_run
from TOOL_RACK_PAPER import assert_previous_runs_flat
from strategy_core.marketdata.kalshi_public import PublicReceipt
from strategy_core.paper_execution import PaperExecutioner
from strategy_core.paper_runtime import GlobalPaperLease
from tests.tool_rack.test_paper_execution import book, decision


TICKER = "KXBTC15M-FIXTURE-A"
CLOSE = 1900.0
NOW = 2000.0


def iso(timestamp):
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()


def official_receipt(*, ticker=TICKER, close_ts=CLOSE, result="no",
                     status="finalized", provisional=False, payout=None):
    market = {"ticker": ticker, "market_type": "binary", "status": status,
              "is_provisional": provisional, "result": result,
              "close_time": iso(close_ts), "settlement_ts": iso(close_ts + 1),
              "settlement_value_dollars": ("1.0000" if result == "yes" else "0.0000")
              if payout is None else payout}
    body = {"market": market}
    digest = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    return PublicReceipt(body, NOW, .01, digest, "/markets/" + ticker)


class StubPublicClient:
    def __init__(self, receipt=None):
        self.receipt = receipt if receipt is not None else official_receipt()
        self.calls = []

    def market(self, ticker):
        self.calls.append(ticker)
        return self.receipt


class PaperReconcileLauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.run = self.root / "STOPPED_PAPER_FIXTURE"
        self.lease = self.root / "global-paper.lock"
        with PaperExecutioner(self.run) as writer:
            opened = writer.execute(decision(ticker=TICKER, budget=10),
                                    book(ticker=TICKER, close_ts=CLOSE),
                                    now_ts=1000., command_id="ORIGINAL_ENTRY")
            self.assertEqual(opened.status, "BOOKED")
            self.assertEqual(opened.event["qty"], 55)
            self.before = writer.snapshot()
        status = {"mode": "PAPER", "state": "STOPPED", "run_id": self.run.name,
                  "stop_reason": "PAPER_ENTRY_WINDOW_FINALITY_TIMEOUT_UNRESOLVED",
                  "ledger_seq": self.before["journal_seq"],
                  "ledger_sha256": self.before["journal_sha256"],
                  "final_ledger_seq": self.before["journal_seq"],
                  "final_ledger_sha256": self.before["journal_sha256"],
                  "unresolved_inventory_count": 1,
                  "positions": self.before["positions"]}
        for name, value in (("PAPER_LEDGER.json", self.before),
                            ("STATUS.json", status), ("RUN_SUMMARY.json", status),
                            ("RUN_MANIFEST.json", {"mode": "PAPER", "run_id": self.run.name})):
            (self.run / name).write_text(json.dumps(value), encoding="utf-8")
        self.original_journal = self.journal_bytes()
        self.client = StubPublicClient()

    def tearDown(self):
        self.temp.cleanup()

    def journal_bytes(self):
        return {p.name: p.read_bytes() for p in (self.run / "paper_journal").glob("*.json")}

    def reconcile(self, client=None, **kwargs):
        return repair.reconcile_runs([self.run], lease_path=self.lease,
                                     client=self.client if client is None else client,
                                     now_ts=NOW, **kwargs)[0]

    def read_json(self, name):
        return json.loads((self.run / name).read_text(encoding="utf-8"))

    def assert_economics_unchanged(self):
        self.assertEqual(self.journal_bytes(), self.original_journal)
        checked = PaperExecutioner.inspect_journal(self.run)
        self.assertEqual(checked["sha256"], self.before["journal_sha256"])
        self.assertEqual(len(checked["state"]["positions"]), 1)
        self.assertEqual(checked["state"]["cash"], self.before["cash"])

    def test_blocked_start_gives_repair_instruction_without_new_session_or_pointer_change(self):
        pointer = self.lease.with_name("paper_last_run.json")
        pointer.write_text(json.dumps({"mode": "PAPER", "run_dir": str(self.run)}), encoding="utf-8")
        original_pointer = pointer.read_bytes()
        output = self.root / "next-output"
        with patch.object(launch, "global_lease_path", return_value=self.lease), \
                patch.object(launch, "run_session", side_effect=AssertionError("No session allowed")), \
                patch("sys.stdout", new_callable=io.StringIO) as printed:
            code = launch.main(["--output-root", str(output), "--no-browser"])
        self.assertEqual(code, 2)
        self.assertIn("05_RECONCILE_PREVIOUS_TOOL_RACK_RUN.cmd", printed.getvalue())
        self.assertNotIn("Traceback", printed.getvalue())
        self.assertEqual(pointer.read_bytes(), original_pointer)
        self.assertFalse(list(output.glob("TOOL_RACK_PAPER_*")))
        self.assertFalse((output / "LAST_RUN.json").exists())
        self.assert_economics_unchanged()

    def test_losing_settlement_recognizes_cost_once_without_second_cash_debit(self):
        report = self.reconcile()
        after = PaperExecutioner.inspect_journal(self.run)["state"]
        self.assertEqual(report["status"], "COMPLETE_FLAT")
        self.assertEqual(report["settled_position_ids"], ["1"])
        self.assertFalse(after["positions"])
        self.assertEqual(Decimal(after["cash"]), Decimal("990.10"))
        self.assertEqual(Decimal(after["cash"]), Decimal(self.before["cash"]))
        self.assertEqual(Decimal(after["realized_gross"]), Decimal("-9.3500"))
        self.assertEqual(Decimal(after["realized_net"]), Decimal("-9.9000"))
        self.assertEqual(Decimal(after["fees_paid"]), Decimal("0.55"))
        self.assertEqual(after["events"][-1]["event"], "SETTLEMENT")
        self.assertEqual(Decimal(after["events"][-1]["fees"]), Decimal(0))

    def test_winning_settlement_credits_exact_remaining_quantity_once(self):
        report = self.reconcile(StubPublicClient(official_receipt(result="yes")))
        after = PaperExecutioner.inspect_journal(self.run)["state"]
        self.assertEqual(report["status"], "COMPLETE_FLAT")
        self.assertEqual(Decimal(after["cash"]), Decimal("1045.10"))
        self.assertEqual(Decimal(after["realized_gross"]), Decimal("45.6500"))
        self.assertEqual(Decimal(after["realized_net"]), Decimal("45.1000"))
        self.assertEqual(Decimal(after["fees_paid"]), Decimal("0.55"))
        self.assertEqual(Decimal(after["events"][-1]["cash_delta"]), Decimal(55))

    def test_append_only_settlement_has_verified_original_backup_and_receipt(self):
        original = {p.relative_to(self.run).as_posix(): p.read_bytes()
                    for p in self.run.rglob("*.json")}
        report = self.reconcile()
        current = self.journal_bytes()
        self.assertEqual(len(current), len(self.original_journal) + 1)
        for name, data in self.original_journal.items():
            self.assertEqual(current[name], data)
        backup = Path(report["backup_path"])
        self.assertEqual(hashlib.sha256(backup.read_bytes()).hexdigest(), report["backup_sha256"])
        with zipfile.ZipFile(backup) as archive:
            self.assertIsNone(archive.testzip())
            manifest = json.loads(archive.read("BACKUP_MANIFEST.json"))
            self.assertEqual(manifest["journal_seq"], self.before["journal_seq"])
            self.assertEqual(manifest["journal_sha256"], self.before["journal_sha256"])
            for name, data in original.items():
                self.assertEqual(archive.read(name), data)
                self.assertEqual(manifest["files"][name], hashlib.sha256(data).hexdigest())
        attempt = Path(report["report_path"]).parent
        receipts = json.loads((attempt / "official_receipts.json").read_text(encoding="utf-8"))
        self.assertEqual(receipts[0]["route"], "/markets/" + TICKER)
        self.assertEqual(receipts[0]["body"]["market"]["result"], "no")
        self.assertEqual(json.loads(Path(report["report_path"]).read_text(encoding="utf-8"))["status"],
                         "COMPLETE_FLAT")
        self.assertFalse((self.run / "paper_writer.lock").exists())

    def test_all_stopped_projections_point_to_final_verified_boundary(self):
        report = self.reconcile()
        checked = PaperExecutioner.inspect_journal(self.run)
        ledger = self.read_json("PAPER_LEDGER.json")
        self.assertEqual(ledger["journal_seq"], checked["seq"])
        self.assertEqual(ledger["journal_sha256"], checked["sha256"])
        self.assertEqual(ledger["positions"], {})
        for name in ("STATUS.json", "RUN_SUMMARY.json"):
            value = self.read_json(name)
            self.assertEqual(value["state"], "STOPPED")
            self.assertEqual(value["mode"], "PAPER")
            self.assertEqual(value["ledger_seq"], checked["seq"])
            self.assertEqual(value["final_ledger_seq"], checked["seq"])
            self.assertEqual(value["ledger_sha256"], checked["sha256"])
            self.assertEqual(value["final_ledger_sha256"], checked["sha256"])
            self.assertEqual(value["unresolved_inventory_count"], 0)
            self.assertEqual(value["cash"], ledger["cash"])
            self.assertEqual(value["post_run_reconciliation"]["report_path"], report["report_path"])
            self.assertEqual(value["original_stop_reason"], "PAPER_ENTRY_WINDOW_FINALITY_TIMEOUT_UNRESOLVED")

    def test_direct_and_two_pointer_paths_deduplicate_without_rewriting_pointers(self):
        pointers = (self.root / "paper_last_run.json", self.root / "LAST_RUN.json")
        for pointer in pointers:
            pointer.write_text(json.dumps({"run_dir": str(self.run), "mode": "PAPER"}), encoding="utf-8")
        before = {p: p.read_bytes() for p in pointers}
        with self.assertRaisesRegex(RuntimeError, "INVENTORY_UNRESOLVED"):
            assert_previous_runs_flat(*pointers)
        reports = repair.reconcile_runs([self.run], pointers=pointers,
                                        lease_path=self.lease, client=self.client, now_ts=NOW)
        self.assertEqual(len(reports), 1)
        self.assertEqual(self.client.calls, [TICKER])
        self.assertEqual({p: p.read_bytes() for p in pointers}, before)
        assert_previous_runs_flat(*pointers)

    def test_idempotent_rerun_uses_no_second_request_or_economic_commit(self):
        self.reconcile()
        journal = self.journal_bytes()
        boundary = PaperExecutioner.inspect_journal(self.run)
        second = self.reconcile()
        self.assertEqual(second["status"], "COMPLETE_FLAT")
        self.assertEqual(second["settled_position_ids"], [])
        self.assertEqual(self.client.calls, [TICKER])
        self.assertEqual(self.journal_bytes(), journal)
        self.assertEqual(second["after_journal_seq"], boundary["seq"])
        self.assertEqual(second["after_journal_sha256"], boundary["sha256"])

    def test_nonfinal_wrong_ticker_wrong_close_or_payout_cannot_change_economics(self):
        cases = [official_receipt(status="closed"), official_receipt(provisional=True),
                 official_receipt(ticker="KXBTC15M-OTHER"), official_receipt(close_ts=CLOSE + 1),
                 official_receipt(payout="1.0000")]
        for receipt in cases:
            with self.subTest(receipt=receipt.body):
                with self.assertRaises(RuntimeError):
                    self.reconcile(StubPublicClient(receipt))
                self.assert_economics_unchanged()
                self.assertFalse((self.run / "paper_writer.lock").exists())

    def test_unexpired_position_stays_unresolved_without_public_request(self):
        with self.assertRaisesRegex(ValueError, "UNEXPIRED_POSITION"):
            repair.reconcile_runs([self.run], lease_path=self.lease,
                                  client=self.client, now_ts=CLOSE - 1)
        self.assertEqual(self.client.calls, [])
        self.assert_economics_unchanged()

    def test_nonstopped_or_nonpaper_run_is_refused(self):
        original = self.read_json("STATUS.json")
        for changes in ({"state": "RUNNING"}, {"state": "DRAINING"}, {"mode": "LIVE"}):
            with self.subTest(changes=changes):
                (self.run / "STATUS.json").write_text(json.dumps({**original, **changes}), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "STOPPED_PAPER_RUN"):
                    self.reconcile()
                self.assert_economics_unchanged()
        self.assertEqual(self.client.calls, [])

    def test_global_engine_lease_blocks_reconciliation(self):
        with GlobalPaperLease(self.lease):
            with self.assertRaisesRegex(RuntimeError, "ANOTHER_TOOL_RACK_PAPER_ENGINE"):
                self.reconcile()
        self.assertEqual(self.client.calls, [])
        self.assert_economics_unchanged()

    def test_existing_writer_lock_is_preserved_and_blocks_reconciliation(self):
        lock = self.run / "paper_writer.lock"
        lock.write_bytes(b"original-lock-evidence")
        with self.assertRaisesRegex(RuntimeError, "PAPER_WRITER_LOCK_EXISTS"):
            self.reconcile()
        self.assertEqual(lock.read_bytes(), b"original-lock-evidence")
        self.assertEqual(self.client.calls, [])
        self.assert_economics_unchanged()

    def test_uncommitted_temporary_journal_requires_review(self):
        pending = self.run / "paper_journal" / ".00000003.interrupted.tmp"
        pending.write_bytes(b"uncommitted evidence")
        with self.assertRaisesRegex(ValueError, "UNCOMMITTED_JOURNAL"):
            self.reconcile()
        self.assertEqual(pending.read_bytes(), b"uncommitted evidence")
        self.assertEqual(self.client.calls, [])
        self.assert_economics_unchanged()

    def test_failed_receipt_publication_cannot_silently_settle(self):
        original_atomic = repair.atomic_json

        def unavailable(path, value, **kwargs):
            return False if path.name == "official_receipts.json" else original_atomic(path, value, **kwargs)

        with patch.object(repair, "atomic_json", side_effect=unavailable):
            with self.assertRaises(RuntimeError):
                self.reconcile()
        self.assert_economics_unchanged()

    def test_retry_after_projection_failure_never_debits_or_settles_twice(self):
        original_atomic = repair.atomic_json

        def unavailable(path, value, **kwargs):
            return False if path == self.run / "STATUS.json" else original_atomic(path, value, **kwargs)

        with patch.object(repair, "atomic_json", side_effect=unavailable):
            with self.assertRaises(RuntimeError):
                self.reconcile()
        committed = PaperExecutioner.inspect_journal(self.run)
        self.assertFalse(committed["state"]["positions"])
        self.assertEqual(len(committed["state"]["events"]), 2)
        self.assertEqual(Decimal(committed["state"]["cash"]), Decimal("990.10"))
        self.assertEqual(self.read_json("STATUS.json")["unresolved_inventory_count"], 1)
        retry = self.reconcile()
        after = PaperExecutioner.inspect_journal(self.run)
        self.assertEqual(retry["settled_position_ids"], [])
        self.assertEqual(after["sha256"], committed["sha256"])
        self.assertEqual(after["state"], committed["state"])
        self.assertEqual(self.client.calls, [TICKER])
        self.assertEqual(self.read_json("STATUS.json")["unresolved_inventory_count"], 0)
        self.assertEqual(self.read_json("RUN_SUMMARY.json")["final_ledger_seq"], committed["seq"])

    def test_export_retains_reconciliation_backup_receipt_and_report(self):
        report = self.reconcile()
        exported = export_run(self.run)
        attempt = Path(report["report_path"]).parent.relative_to(self.run)
        with zipfile.ZipFile(exported) as archive:
            manifest = json.loads(archive.read(self.run.name + "/EXPORT_MANIFEST.json"))
            for name in ("before.zip", "official_receipts.json", "report.json"):
                relative = (attempt / name).as_posix()
                data = archive.read(self.run.name + "/" + relative)
                self.assertEqual(data, (self.run / relative).read_bytes())
                self.assertEqual(manifest["files"][relative], hashlib.sha256(data).hexdigest())
            self.assertTrue(manifest["journal_verified"])
            self.assertEqual(manifest["journal_seq"], report["after_journal_seq"])


if __name__ == "__main__":
    unittest.main()
