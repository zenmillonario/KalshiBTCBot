"""Settlement-only recovery preserves a stopped PAPER journal and its limits."""
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from strategy_core.commander import CommanderDecision
from strategy_core.paper_execution import (
    FloorPolicy, OfficialResult, PaperExecutionError, PaperExecutioner,
)
from strategy_core.types import Action, Side
from tests.tool_rack.test_paper_execution import book, decision


class SettlementRecoveryAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run = self.root / "stopped_run"
        with PaperExecutioner(self.run) as writer:
            receipt = writer.execute(decision(), book(), now_ts=1000., command_id="ORIGINAL_ENTRY")
            self.assertEqual(receipt.status, "BOOKED")
        self.before = PaperExecutioner.inspect_journal(self.run)
        self.original_bytes = {p.name: p.read_bytes() for p in (self.run / "paper_journal").glob("*.json")}

    def recovery(self, **overrides):
        options = {"settlement_only": True, "expected_journal_seq": self.before["seq"],
                   "expected_journal_sha256": self.before["sha256"]}
        options.update(overrides)
        return PaperExecutioner(self.run, **options)

    @staticmethod
    def result(side=Side.NO):
        return OfficialResult("KX1", "EXACT_FINAL_RESULT", side, 1900., 1901., "KALSHI_PUBLIC_TLS_GET",
                              provenance={"fixture": "verified exact-contract parser result"})

    def assert_original_bytes_retained(self):
        for filename, data in self.original_bytes.items():
            self.assertEqual((self.run / "paper_journal" / filename).read_bytes(), data)

    def assert_unchanged(self):
        after = PaperExecutioner.inspect_journal(self.run)
        self.assertEqual(after, self.before)
        self.assert_original_bytes_retained()
        self.assertFalse((self.run / "paper_writer.lock").exists())

    def test_recovery_loads_exact_lot_and_appends_only_official_settlement(self):
        original = deepcopy(self.before["state"])
        with self.recovery() as writer:
            snapshot = writer.snapshot()
            for key, value in original.items():
                self.assertEqual(snapshot[key], value)
            self.assertEqual(snapshot["journal_seq"], self.before["seq"])
            self.assertEqual(snapshot["journal_sha256"], self.before["sha256"])
            receipts = writer.settle(self.result())
            self.assertEqual(len(receipts), 1)
            self.assertEqual(receipts[0].status, "SETTLED")
            self.assertEqual(receipts[0].event["qty"], 138)
            self.assertEqual(Decimal(receipts[0].event["price"]), Decimal(0))
            self.assertEqual(Decimal(receipts[0].event["net_pnl"]), Decimal("-24.83"))
            self.assertFalse(writer.positions)
        after = PaperExecutioner.inspect_journal(self.run)
        self.assertEqual(after["seq"], self.before["seq"] + 1)
        self.assertEqual(after["state"]["cash"], original["cash"])
        self.assertEqual(after["state"]["fees_paid"], original["fees_paid"])
        self.assertEqual(after["state"]["closed_positions"]["1"], original["positions"]["1"])
        self.assertEqual(after["state"]["events"][:-1], original["events"])
        self.assertEqual(after["state"]["consumed_opportunities"], original["consumed_opportunities"])
        latest = json.loads((self.run / "paper_journal" / f"{after['seq']:08d}.json").read_text(encoding="utf-8"))
        self.assertEqual(latest["kind"], "OFFICIAL_SETTLEMENT")
        self.assertEqual(latest["previous_sha256"], self.before["sha256"])
        self.assert_original_bytes_retained()

    def test_winning_settlement_pays_exact_quantity_without_new_fee_or_basis(self):
        original = self.before["state"]
        with self.recovery() as writer:
            event = writer.settle(self.result(Side.YES))[0].event
            self.assertEqual(Decimal(event["cash_delta"]), Decimal(138))
            self.assertEqual(Decimal(event["fees"]), Decimal(0))
            self.assertEqual(Decimal(event["net_pnl"]), Decimal("113.17"))
        state = PaperExecutioner.inspect_journal(self.run)["state"]
        self.assertEqual(Decimal(state["cash"]), Decimal(original["cash"]) + 138)
        self.assertEqual(state["fees_paid"], original["fees_paid"])
        self.assert_original_bytes_retained()

    def test_duplicate_result_is_idempotent_in_same_and_reopened_recovery(self):
        with self.recovery() as writer:
            writer.settle(self.result())
            settled = writer.snapshot()
            self.assertEqual(writer.settle(self.result())[0].status, "DUPLICATE")
            self.assertEqual(writer.snapshot(), settled)
        with PaperExecutioner(self.run, settlement_only=True,
                              expected_journal_seq=settled["journal_seq"],
                              expected_journal_sha256=settled["journal_sha256"]) as writer:
            self.assertEqual(writer.snapshot(), settled)
            self.assertEqual(writer.settle(self.result())[0].status, "DUPLICATE")
            self.assertEqual(writer.snapshot(), settled)

    def test_trade_floor_custody_and_nonsettlement_commits_are_denied(self):
        custody = CommanderDecision(Action.HOLD, None, "QUALIFIED_FIXTURE_CUSTODY", custody_update={
            "position_id": "1", "previous_state": "NORMAL", "state": "LAZARUS",
            "reviewed_at": 1001., "reason": "EXPLICIT_RECOVERY_FIXTURE",
            "review": {"lazarus_qualified": True, "hard_exit": False}})
        with self.recovery() as writer:
            blocked = [
                lambda: writer.execute(decision(1001), book(1001), now_ts=1001., command_id="NEW_ENTRY"),
                lambda: writer.execute(decision(1001, action=Action.EXIT), book(1001),
                                       now_ts=1001., command_id="NEW_EXIT", position_id="1"),
                lambda: writer.observe_floors(book(1040, yes=.9), now_ts=1040.,
                                              policies={"1": FloorPolicy(.1, .1)}),
                lambda: writer.record_custody(custody, position_id="1", now_ts=1001.),
            ]
            for operation in blocked:
                with self.assertRaisesRegex(PaperExecutionError, "FORBIDS_NONSETTLEMENT_WRITES"):
                    operation()
            for kind in ("BASELINE", "ENTRY", "EXIT", "CUSTODY", "FLOOR_OBSERVATION", "UNKNOWN"):
                with self.subTest(kind=kind), self.assertRaisesRegex(
                        PaperExecutionError, "FORBIDS_NONSETTLEMENT_WRITES"):
                    writer._commit(deepcopy(self.before["state"]), kind, None)
        self.assert_unchanged()

    def test_missing_or_empty_journal_cannot_create_fresh_baseline(self):
        missing = self.root / "missing_run"
        with self.assertRaisesRegex(PaperExecutionError, "REQUIRES_EXISTING_JOURNAL"):
            PaperExecutioner(missing, settlement_only=True)
        self.assertFalse(missing.exists())
        empty = self.root / "empty_run"
        (empty / "paper_journal").mkdir(parents=True)
        with self.assertRaisesRegex(PaperExecutionError, "REQUIRES_EXISTING_JOURNAL"):
            PaperExecutioner(empty, settlement_only=True)
        self.assertEqual(list((empty / "paper_journal").iterdir()), [])
        self.assertFalse((empty / "paper_writer.lock").exists())

    def test_changed_head_hash_or_sequence_is_refused_without_writes(self):
        for changes in ({"expected_journal_sha256": "0" * 64},
                        {"expected_journal_seq": self.before["seq"] + 1}):
            with self.subTest(changes=changes), self.assertRaisesRegex(PaperExecutionError, "JOURNAL_HEAD_CHANGED"):
                self.recovery(**changes)
            self.assert_unchanged()

    def test_existing_writer_lock_is_not_removed_or_overridden(self):
        with self.recovery():
            owner = (self.run / "paper_writer.lock").read_bytes()
            with self.assertRaisesRegex(PaperExecutionError, "WRITER_LOCK_EXISTS"):
                self.recovery()
            self.assertEqual((self.run / "paper_writer.lock").read_bytes(), owner)
        self.assert_unchanged()
        (self.run / "paper_writer.lock").write_text('{"pid": 999999, "token": "unreviewed"}', encoding="utf-8")
        with self.assertRaisesRegex(PaperExecutionError, "WRITER_LOCK_EXISTS"):
            self.recovery()
        self.assertTrue((self.run / "paper_writer.lock").exists())

    def test_normal_resume_still_refuses_open_inventory_and_modes_cannot_mix(self):
        with self.assertRaisesRegex(PaperExecutionError, "OPEN_INVENTORY"):
            PaperExecutioner(self.run, resume=True)
        with self.assertRaisesRegex(ValueError, "ARE_EXCLUSIVE"):
            self.recovery(resume=True)
        self.assert_unchanged()

    def test_invalid_result_or_conflict_does_not_rewrite_committed_accounting(self):
        with self.recovery() as writer:
            initial = writer.snapshot()
            invalid = [OfficialResult("KX1", "R", Side.NO, 1900., 1901., "BTC_PROXY"),
                       OfficialResult("KX1", "R", Side.NO, 1901., 1902., "KALSHI_PUBLIC_TLS_GET"),
                       OfficialResult("KX1", "R", Side.NO, 1900., 1899., "KALSHI_PUBLIC_TLS_GET")]
            for result in invalid:
                with self.assertRaises(ValueError):
                    writer.settle(result)
                self.assertEqual(writer.snapshot(), initial)
            self.assertEqual(writer.settle(OfficialResult("OTHER", "R", Side.NO, 1900., 1901.,
                                                        "KALSHI_PUBLIC_TLS_GET")), ())
            self.assertEqual(writer.snapshot(), initial)
            writer.settle(self.result())
            settled = writer.snapshot()
            with self.assertRaisesRegex(PaperExecutionError, "CONFLICTING_OFFICIAL_RESULT"):
                writer.settle(self.result(Side.YES))
            self.assertEqual(writer.snapshot(), settled)
        self.assert_original_bytes_retained()

    def test_failed_settlement_commit_retains_original_boundary(self):
        with self.recovery() as writer:
            with patch("strategy_core.paper_execution.os.replace", side_effect=OSError("disk full")):
                with self.assertRaisesRegex(PaperExecutionError, "COMMIT_FAILED"):
                    writer.settle(self.result())
            after = PaperExecutioner.inspect_journal(self.run)
            self.assertEqual(after["sha256"], self.before["sha256"])
            self.assertEqual(after["seq"], self.before["seq"])
            self.assertEqual(after["state"], self.before["state"])
        self.assert_original_bytes_retained()
        self.assertFalse((self.run / "paper_writer.lock").exists())

    def test_corrupt_existing_journal_is_refused_without_a_replacement_baseline(self):
        path = self.run / "paper_journal" / f"{self.before['seq']:08d}.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw["state"]["cash"] = "1000"
        path.write_text(json.dumps(raw), encoding="utf-8")
        with self.assertRaisesRegex(PaperExecutionError, "JOURNAL_INTEGRITY"):
            self.recovery()
        self.assertEqual(len(list((self.run / "paper_journal").glob("*.json"))), self.before["seq"])
        self.assertFalse((self.run / "paper_writer.lock").exists())


if __name__ == "__main__":
    unittest.main()
