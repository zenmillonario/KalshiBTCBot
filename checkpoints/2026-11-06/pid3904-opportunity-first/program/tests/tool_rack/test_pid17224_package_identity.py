"""Release provenance cannot hide an unapproved core/configuration change."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from CHECK_TOOL_RACK_PAPER import (
    APPROVED_CHANGED_CORE_FILES, APPROVED_ADDED_CORE_FILES, verify_authorized_delta, verify_frozen_source,
)


ROOT = Path(__file__).resolve().parents[2]


class PID17224PackageIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="pid17224_identity_")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        current = json.loads((ROOT / "SOURCE_SHA256.json").read_text(encoding="utf-8"))
        for name in (*current, "SOURCE_SHA256.json", "BASELINE_SOURCE_SHA256.json",
                     "APPROVED_STRATEGY_CHANGES.json", "PREVIOUS_RELEASE_SOURCE_SHA256.json",
                     "PREVIOUS_RELEASE_APPROVAL.json", "PID19996_SOURCE_SHA256.json",
                     "PID19996_APPROVAL.json", "PID4596_SOURCE_SHA256.json", "PID4596_APPROVAL.json",
                     "PID17588_SOURCE_SHA256.json", "PID17588_APPROVAL.json",
                     "PID15184_SOURCE_SHA256.json", "PID15184_APPROVAL.json",
                     "PID4824_SOURCE_SHA256.json", "PID4824_APPROVAL.json",
                     "PID3904_SOURCE_SHA256.json", "PID3904_APPROVAL.json"):
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)

    def reseal_file(self, name):
        path = self.root / "SOURCE_SHA256.json"
        current = json.loads(path.read_text(encoding="utf-8"))
        current[name] = hashlib.sha256((self.root / name).read_bytes()).hexdigest()
        path.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def test_new_delta_preserves_the_pinned_historical_two_file_approval(self):
        self.assertEqual(verify_frozen_source(self.root), 68)
        delta = verify_authorized_delta(self.root)
        self.assertEqual(set(delta["changed_files"]), APPROVED_CHANGED_CORE_FILES)
        self.assertEqual(delta["unchanged_files"], 67 - len(APPROVED_CHANGED_CORE_FILES))
        self.assertEqual(set(delta["added_files"]), APPROVED_ADDED_CORE_FILES)
        self.assertEqual(set(delta["pid19996_added_files"]), {"strategy_core/source_freshness.py"})
        self.assertEqual(len(delta["pid19996_changed_files"]), 12)
        self.assertEqual(set(delta["pid4596_changed_files"]), {"strategy_core/mission_policy.py", "strategy_core/paper_runtime.py"})
        self.assertEqual(set(delta["pid17588_changed_files"]), {"strategy_core/commander_candidates.py", "strategy_core/paper_runtime.py"})
        self.assertEqual(set(delta["pid15184_changed_files"]), {"strategy_core/dual_lane.py", "strategy_core/tool_rack.py", "strategy_core/paper_runtime.py"})
        self.assertEqual(set(delta["pid4824_changed_files"]), {"strategy_core/tool_rack.py", "strategy_core/paper_runtime.py"})
        self.assertEqual(set(delta["historical_changed_files"]), {"strategy_core/commander.py", "strategy_core/commander_candidates.py"})

    def test_previous_release_seal_cannot_be_replaced_to_hide_changes(self):
        with (self.root / "PREVIOUS_RELEASE_SOURCE_SHA256.json").open("ab") as handle:
            handle.write(b"\n")
        with self.assertRaisesRegex(ValueError, "Previous release source manifest changed"):
            verify_frozen_source(self.root)

    def test_added_helper_requires_exact_reviewed_hash(self):
        name = "strategy_core/source_freshness.py"
        with (self.root / name).open("ab") as handle:
            handle.write(b"\n# unreviewed helper change\n")
        self.reseal_file(name)
        with self.assertRaisesRegex(ValueError, "Core changes differ from approved Opportunity-First scope"):
            verify_frozen_source(self.root)

    def test_pid19996_source_identity_cannot_be_replaced_to_hide_changes(self):
        with (self.root / "PID19996_SOURCE_SHA256.json").open("ab") as handle:
            handle.write(b"\n")
        with self.assertRaisesRegex(ValueError, "PID19996 source manifest changed"):
            verify_frozen_source(self.root)

    def test_pid4596_source_identity_cannot_be_replaced_to_hide_changes(self):
        with (self.root / "PID4596_SOURCE_SHA256.json").open("ab") as handle:
            handle.write(b"\n")
        with self.assertRaisesRegex(ValueError, "PID4596 source manifest changed"):
            verify_frozen_source(self.root)

    def test_pid17588_source_identity_cannot_be_replaced_to_hide_changes(self):
        with (self.root / "PID17588_SOURCE_SHA256.json").open("ab") as handle:
            handle.write(b"\n")
        with self.assertRaisesRegex(ValueError, "PID17588 source manifest changed"):
            verify_frozen_source(self.root)

    def test_pid15184_source_identity_cannot_be_replaced_to_hide_changes(self):
        with (self.root / "PID15184_SOURCE_SHA256.json").open("ab") as handle:
            handle.write(b"\n")
        with self.assertRaisesRegex(ValueError, "PID15184 source manifest changed"):
            verify_frozen_source(self.root)

    def test_pid4824_source_identity_cannot_be_replaced_to_hide_changes(self):
        with (self.root / "PID4824_SOURCE_SHA256.json").open("ab") as handle:
            handle.write(b"\n")
        with self.assertRaisesRegex(ValueError, "PID4824 source manifest changed"):
            verify_frozen_source(self.root)

    def test_pid4824_approval_identity_cannot_be_replaced_to_hide_changes(self):
        with (self.root / "PID4824_APPROVAL.json").open("ab") as handle:
            handle.write(b"\n")
        with self.assertRaisesRegex(ValueError, "PID4824 approval changed"):
            verify_frozen_source(self.root)

    def test_unsealed_source_edit_is_rejected(self):
        with (self.root / "strategy_core/commander.py").open("ab") as handle:
            handle.write(b"\n# post-approval edit\n")
        with self.assertRaisesRegex(ValueError, "Sealed strategy/config/UI source changed"):
            verify_frozen_source(self.root)

    def test_resealing_unapproved_configuration_cannot_expand_scope(self):
        name = "strategy_core/config/mission.json"
        with (self.root / name).open("ab") as handle:
            handle.write(b"\n ")
        self.reseal_file(name)
        with self.assertRaisesRegex(ValueError, "Core changes differ from approved Opportunity-First scope"):
            verify_frozen_source(self.root)

    def test_resealing_approved_file_still_requires_exact_reviewed_hash(self):
        name = "strategy_core/commander.py"
        with (self.root / name).open("ab") as handle:
            handle.write(b"\n# unreviewed further change\n")
        self.reseal_file(name)
        with self.assertRaisesRegex(ValueError, "Approved correction hash mismatch"):
            verify_frozen_source(self.root)

    def test_baseline_manifest_itself_is_pinned_to_original_package(self):
        with (self.root / "BASELINE_SOURCE_SHA256.json").open("ab") as handle:
            handle.write(b"\n")
        with self.assertRaisesRegex(ValueError, "captured baseline source manifest changed"):
            verify_frozen_source(self.root)

    def test_pid3904_immediate_source_and_approval_records_are_pinned(self):
        for name, message in (("PID3904_SOURCE_SHA256.json", "Captured PID3904 immediate source manifest changed"),
                              ("PID3904_APPROVAL.json", "Captured PID3904 immediate approval record changed")):
            original=(self.root/name).read_bytes()
            try:
                (self.root/name).write_bytes(original+b"\n")
                with self.assertRaisesRegex(ValueError,message):
                    verify_frozen_source(self.root)
            finally:
                (self.root/name).write_bytes(original)

    def test_new_opportunity_helper_requires_exact_reviewed_hash(self):
        name="strategy_core/opportunity_first.py"
        with (self.root/name).open("ab") as handle:
            handle.write(b"\n# unreviewed opportunity change\n")
        self.reseal_file(name)
        with self.assertRaisesRegex(ValueError,"Approved Opportunity-First helper hash mismatch"):
            verify_frozen_source(self.root)


if __name__ == "__main__":
    unittest.main()
