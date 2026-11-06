"""Targeted transport checks; no trading engine is imported or exercised."""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile


ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import make_upload_parts as helper

RUN_NAME = "SYNTHETIC_EXACT_NEW_PAPER_RUN"
PREFIX = "original/" + RUN_NAME + "/"


def fixture_members(*, run_id=RUN_NAME, program_state="MATCHED_CAPTURE", optional=None):
    prefix = "original/" + run_id + "/"
    j = lambda value: (json.dumps(value, sort_keys=True) + "\r\n").encode()
    originals = {
        "RUN_MANIFEST.json": j({"run_id": run_id, "mode": "PAPER", "files": {}}),
        "RUN_SUMMARY.json": j({"run_id": run_id, "mode": "PAPER", "state": "STOPPED", "cash": "1038.84"}),
        "PAPER_LEDGER.json": j({"cash": "1038.84", "fixture": True}),
        "STATUS.json": j({"state": "STOPPED"}),
        "CAPTURE_STATUS.json": j({"complete": True, "writer_alive": False}),
        "ENGINE_OUTPUTS.json": j({"files": {}}),
        "replay_capture/engine_inputs.manifest.json": j({"complete": True}),
        "paper_journal/00000001.json": j({"seq": 1, "original_bytes": "retained"}),
        "paper_journal/00000002.json": j({"seq": 2, "original_bytes": "retained too"}),
        "console.log": b"Exact console bytes\r\nnot normalized\r\n",
        "leg_performance.jsonl": b'{"leg":"synthetic"}\r\n',
        "mission_history.jsonl": b'{"mission":"synthetic"}\r\n',
        "decisions.jsonl": (b'{"large_decision":"synthetic"}\n' * 73),
        "replay_capture/engine_inputs.jsonl": b'{"original_tape":"bytes preserved"}\r\n',
        "btc_public_source.jsonl.gz": b"\x1f\x8bSynthetic compressed transport bytes\x00\xff",
    }
    if optional:
        originals.update(optional)
    members = {prefix + name: data for name, data in originals.items()}
    members["program/SOURCE_SHA256.json"] = j({"fixture.py": "fixture-sha"})
    members["program/fixture.py"] = b"# captured program must survive transport exactly\r\n"
    members["COMPLETION_REPORT.json"] = j({
        "run_id": run_id, "mode": "PAPER", "capture": {"state": "REPORTED_COMPLETE"},
        "program": {"state": program_state},
        "replay": {"state": "NOT_REQUESTED", "performed": False},
        "export": {"state": "VERIFIED_ON_ATOMIC_PUBLICATION"},
        "files": {name: {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                  for name, data in members.items()},
    })
    return members


def write_archive(path, members):
    with zipfile.ZipFile(path, "x", zipfile.ZIP_STORED) as archive:
        for name, data in members.items():
            archive.writestr(name, data)


class UploadPartsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="tachyos_upload_parts_")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.results = self.root / "PAPER_RESULTS"
        self.results.mkdir()
        self.source = self.results / (RUN_NAME + "_FULL_ORIGINAL_RECOVERY_TEST.zip")
        self.members = fixture_members()
        write_archive(self.source, self.members)
        self.before = self.source.read_bytes()
        self.stream = io.StringIO()
        self.status = self.root / "UPLOAD_STATUS.json"

    def run_helper(self, **options):
        defaults = {"results_dir": self.results, "status_file": self.status,
                    "chunk_bytes": 4096, "stream": self.stream,
                    "source": self.source, "expected_run_id": RUN_NAME}
        defaults.update(options)
        return helper.make_uploads(**defaults)

    def test_complete_archive_roundtrip_and_every_review_byte_are_exact(self):
        result = self.run_helper()
        self.assertEqual(result["state"], "COMPLETE", result)
        self.assertTrue(result["all_verified"])
        self.assertGreater(len(result["parts"]), 1)
        restored = bytearray()
        manifest = json.loads((Path(result["output_dir"]) / "TRANSFER_MANIFEST.json").read_bytes())
        for index, part in enumerate(result["parts"], 1):
            self.assertLess(Path(part).stat().st_size, helper.MAX_ZIP_BYTES)
            with zipfile.ZipFile(part) as archive:
                info = json.loads(archive.read("PART_INFO.json"))
                self.assertEqual(info["part_number"], index)
                payload = archive.read(helper.PAYLOAD_NAME)
                self.assertEqual(hashlib.sha256(payload).hexdigest(), info["sha256"])
                self.assertEqual(len(payload), info["bytes"])
                restored.extend(payload)
                if index == len(result["parts"]):
                    self.assertEqual(json.loads(archive.read("TRANSFER_MANIFEST.json")), manifest)
        self.assertEqual(bytes(restored), self.before)
        self.assertEqual(result["source_sha256"], hashlib.sha256(self.before).hexdigest())
        self.assertEqual(self.source.read_bytes(), self.before)
        with zipfile.ZipFile(result["review_zip"]) as review:
            scope = json.loads(review.read("REVIEW_SCOPE.json"))
            self.assertFalse(scope["complete_recording"])
            self.assertFalse(scope["replay_performed_by_this_helper"])
            self.assertEqual(scope["truncated_members"], [])
            for record in scope["included_members"]:
                self.assertEqual(review.read(record["name"]), self.members[record["name"]])
            for name in self.members:
                if "/paper_journal/" in name:
                    self.assertEqual(review.read(name), self.members[name])
            omissions = {item["name"] for item in scope["omitted_members"]}
            self.assertIn(PREFIX + "decisions.jsonl", omissions)
            self.assertIn(PREFIX + "btc_public_source.jsonl.gz", omissions)
            self.assertIn(PREFIX + "replay_capture/engine_inputs.jsonl", omissions)
            self.assertLessEqual(sum(item.file_size for item in review.infolist()), helper.REVIEW_LIMIT)
            self.assertEqual(json.loads(review.read("TRANSFER_MANIFEST.json")), manifest)
        self.assertEqual(json.loads(self.status.read_bytes())["state"], "COMPLETE")
        self.assertFalse(list(self.results.glob("*.working")))
        self.assertIn("SEND FIRST:", self.stream.getvalue())

    def test_large_uncompressed_journal_does_not_abort_lossless_uploads(self):
        # Regression control for PID18244: the journal can exceed the
        # first-review budget without making the complete archive invalid.
        self.source.unlink()
        large_a = b"A" * 13_000_000
        large_b = b"B" * 13_000_000
        self.members = fixture_members(optional={
            "paper_journal/00000002.json": large_a,
            "paper_journal/00000003.json": large_b,
            "paper_journal/00000004.json": b"small latest journal"})
        write_archive(self.source, self.members)
        before_sha = hashlib.sha256(self.source.read_bytes()).hexdigest()
        result = self.run_helper(chunk_bytes=2_000_000)
        self.assertEqual(result["state"], "COMPLETE", result)
        self.assertTrue(result["all_verified"])
        self.assertEqual(result["source_sha256"], before_sha)
        self.assertTrue(helper.verify_parts(Path(result["output_dir"]),
            json.loads((Path(result["output_dir"]) / "TRANSFER_MANIFEST.json").read_bytes())))
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(), before_sha)
        with zipfile.ZipFile(result["review_zip"]) as review:
            scope = json.loads(review.read("REVIEW_SCOPE.json"))
            self.assertFalse(scope["paper_journal_preview_complete"])
            self.assertEqual(scope["paper_journal_members_in_original"], 4)
            self.assertEqual(scope["paper_journal_members_in_preview"], 3)
            self.assertEqual(scope["truncated_members"], [])
            self.assertIn(PREFIX + "paper_journal/00000002.json", review.namelist())
            self.assertIn(PREFIX + "paper_journal/00000004.json", review.namelist())
            self.assertNotIn(PREFIX + "paper_journal/00000003.json", review.namelist())
            omitted = {x["name"]: x for x in scope["omitted_members"]}
            self.assertIn(PREFIX + "paper_journal/00000003.json", omitted)
            self.assertIn("numbered parts", omitted[PREFIX + "paper_journal/00000003.json"]["reason"])
            self.assertLess(Path(result["review_zip"]).stat().st_size, helper.REVIEW_LIMIT)
        readme = (Path(result["output_dir"]) / "READ_ME_FIRST.txt").read_text(encoding="utf-8")
        self.assertIn("3/4 complete journal members", readme)
        self.assertIn("omitted", readme)

    def test_single_oversized_journal_is_omitted_without_truncation(self):
        self.source.unlink()
        self.members = fixture_members(optional={
            "paper_journal/00000001.json": b"J" * 26_000_000,
            "paper_journal/00000002.json": b"tiny final sample"})
        write_archive(self.source, self.members)
        result = self.run_helper(chunk_bytes=3_000_000)
        self.assertEqual(result["state"], "COMPLETE", result)
        with zipfile.ZipFile(result["review_zip"]) as review:
            scope = json.loads(review.read("REVIEW_SCOPE.json"))
            self.assertEqual(scope["paper_journal_members_in_preview"], 1)
            self.assertFalse(scope["paper_journal_preview_complete"])
            self.assertNotIn(PREFIX + "paper_journal/00000001.json", review.namelist())
            self.assertEqual(review.read(PREFIX + "paper_journal/00000002.json"), b"tiny final sample")
            self.assertEqual(scope["truncated_members"], [])

    def test_journal_review_priority_covers_endpoints_and_middle(self):
        names = [f"journal/{i:08d}.json" for i in range(1, 10)]
        priority = list(helper._journal_review_priority(names))
        self.assertEqual(priority[:3], [names[0], names[-1], names[4-0]])
        self.assertEqual(set(priority), set(names))
        self.assertEqual(len(priority), len(names))

    def test_optional_oversized_file_is_explicitly_omitted_only_from_review(self):
        self.source.unlink()
        self.members = fixture_members(optional={"mission_history.jsonl": b"m" * 1001})
        write_archive(self.source, self.members)
        before = self.source.read_bytes()
        with patch.object(helper, "OPTIONAL_MEMBER_LIMIT", 1000):
            result = self.run_helper()
        self.assertEqual(result["state"], "COMPLETE", result)
        with zipfile.ZipFile(result["review_zip"]) as review:
            name = PREFIX + "mission_history.jsonl"
            self.assertNotIn(name, review.namelist())
            scope = json.loads(review.read("REVIEW_SCOPE.json"))
            omission = next(item for item in scope["omitted_members"] if item["name"] == name)
            self.assertEqual(omission["bytes"], 1001)
            self.assertIn("exceeds", omission["reason"])
        restored = b""
        for part in result["parts"]:
            with zipfile.ZipFile(part) as archive:
                restored += archive.read(helper.PAYLOAD_NAME)
        self.assertEqual(restored, before)

    def test_diagnostic_program_status_is_preserved_without_promoting_it(self):
        self.source.unlink()
        self.members = fixture_members(program_state="NOT_MATCHED")
        write_archive(self.source, self.members)
        result = self.run_helper()
        self.assertEqual(result["state"], "COMPLETE", result)
        self.assertEqual(result["original_report_program_state"], "NOT_MATCHED")
        with zipfile.ZipFile(result["review_zip"]) as review:
            scope = json.loads(review.read("REVIEW_SCOPE.json"))
            self.assertEqual(scope["original_report_program_state"], "NOT_MATCHED")
            self.assertEqual(review.read("COMPLETION_REPORT.json"), self.members["COMPLETION_REPORT.json"])

    def test_corrupted_payload_with_valid_zip_crc_fails_sha_verification(self):
        result = self.run_helper()
        self.assertEqual(result["state"], "COMPLETE", result)
        directory = Path(result["output_dir"])
        manifest = json.loads((directory / "TRANSFER_MANIFEST.json").read_bytes())
        first = Path(result["parts"][0])
        with zipfile.ZipFile(first) as archive:
            members = {name: archive.read(name) for name in archive.namelist()}
        data = bytearray(members[helper.PAYLOAD_NAME])
        data[len(data) // 2] ^= 1
        members[helper.PAYLOAD_NAME] = bytes(data)
        first.unlink()
        write_archive(first, members)
        with self.assertRaisesRegex(helper.UploadError, "checksum failed"):
            helper.verify_parts(directory, manifest)
        self.assertEqual(self.source.read_bytes(), self.before)

    def test_verification_failure_never_publishes_or_claims_complete(self):
        with patch.object(helper, "verify_parts", side_effect=helper.UploadError("Injected damaged piece")):
            result = self.run_helper()
        self.assertEqual(result["state"], "ERROR")
        self.assertFalse(result["all_verified"])
        final_folders = [p for p in self.results.iterdir()
                         if p.is_dir() and "_SMALL_UPLOADS_" in p.name and not p.name.endswith(".working")]
        self.assertEqual(final_folders, [])
        self.assertEqual(self.source.read_bytes(), self.before)
        self.assertEqual(json.loads(self.status.read_bytes())["state"], "ERROR")
        self.assertNotIn("SEND FIRST:", self.stream.getvalue())

    def test_repeat_makes_new_folder_and_never_overwrites_existing_status(self):
        first = self.run_helper()
        self.assertEqual(first["state"], "COMPLETE", first)
        first_status = self.status.read_bytes()
        refusal = self.run_helper()
        self.assertEqual(refusal["state"], "ERROR")
        self.assertEqual(self.status.read_bytes(), first_status)
        before_output = {p.name: p.read_bytes() for p in Path(first["output_dir"]).iterdir() if p.is_file()}
        second = self.run_helper(status_file=self.root / "STATUS_SECOND.json")
        self.assertEqual(second["state"], "COMPLETE", second)
        self.assertNotEqual(first["output_dir"], second["output_dir"])
        self.assertEqual(before_output, {p.name: p.read_bytes() for p in Path(first["output_dir"]).iterdir() if p.is_file()})
        self.assertEqual(self.source.read_bytes(), self.before)

    def test_wrong_run_archive_is_rejected_even_if_filename_looks_right(self):
        self.source.unlink()
        write_archive(self.source, fixture_members(run_id="WRONG_RUN"))
        before = self.source.read_bytes()
        result = self.run_helper()
        self.assertEqual(result["state"], "ERROR")
        self.assertIn("another run", result["error"]["message"])
        self.assertFalse(list(self.results.glob("*SMALL_UPLOADS*")))
        self.assertEqual(self.source.read_bytes(), before)

    def test_source_change_during_copy_prevents_publication(self):
        original = helper.verify_parts
        def verify_then_change(directory, manifest, progress=None):
            result = original(directory, manifest, progress)
            stat = self.source.stat()
            os.utime(self.source, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))
            return result
        with patch.object(helper, "verify_parts", side_effect=verify_then_change):
            result = self.run_helper()
        self.assertEqual(result["state"], "ERROR")
        self.assertIn("changed during", result["error"]["message"])
        self.assertFalse([p for p in self.results.iterdir() if p.is_dir() and not p.name.endswith(".working")])

    def test_disk_space_failure_does_not_start_output_copy(self):
        real = helper.shutil.disk_usage(self.results)
        full = type(real)(total=real.total, used=real.total, free=0)
        with patch.object(helper.shutil, "disk_usage", return_value=full):
            result = self.run_helper()
        self.assertEqual(result["state"], "ERROR")
        self.assertIn("Not enough free disk space", result["error"]["message"])
        self.assertFalse(list(self.results.glob("*SMALL_UPLOADS*")))
        self.assertEqual(self.source.read_bytes(), self.before)

    def test_exact_source_is_required_and_never_replaced_by_newer_run(self):
        newer = self.results / "OTHER_NEWER_RUN_FULL_ORIGINAL.zip"
        write_archive(newer, fixture_members(run_id="OTHER_NEWER_RUN"))
        os.utime(newer, ns=(2_000_000_000, 2_000_000_000))
        with self.assertRaisesRegex(helper.UploadError, "exact completed source ZIP"):
            helper.select_source(self.results)
        self.assertEqual(helper.select_source(self.results, self.source), self.source)
        partial = self.results / "RUN_FULL_ORIGINAL.partial.zip"
        partial.write_bytes(b"unfinished")
        with self.assertRaisesRegex(helper.UploadError, "incomplete"):
            helper.select_source(self.results, partial)

    def test_verified_export_hash_must_match_before_upload_publication(self):
        result = self.run_helper(expected_sha256="0" * 64)
        self.assertEqual(result["state"], "ERROR")
        self.assertIn("verified export SHA256", result["error"]["message"])
        self.assertFalse([p for p in self.results.glob("*SMALL_UPLOADS*") if not p.name.endswith(".working")])
        self.assertEqual(self.source.read_bytes(), self.before)


if __name__ == "__main__":
    unittest.main()
