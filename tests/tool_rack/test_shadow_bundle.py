import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from BUILD_TOOL_RACK_SHADOW_BUNDLE import build


class ShadowBundleSafetyTests(unittest.TestCase):
    def fixture(self):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        required = {
            "CHECK_TOOL_RACK_V1.py": "print('ok')\n",
            "00_CHECK_TOOL_RACK_SHADOW.cmd": "READ ONLY\n",
            "START_TOOL_RACK_SHADOW.cmd": "NO EXECUTION AUTHORITY\n",
            "TOOL_RACK_ATTACH_R22_SHADOW.py": "READ_ONLY=True\n",
            "strategy_core/tool_rack.py": "# rack\n",
            "strategy_core/commander.py": "# commander\n",
            "strategy_core/r22_run_source.py": "# source\n",
            "nautilus_vnext/APPLY_NAUTILUS_VNEXT.py": "# ui\n",
            "nautilus_vnext/APPLY_TOOL_RACK_TIMELINE.py": "# timeline\n",
            "docs/TOOL_RACK_PHASE2_STATUS.md": "# phase2\n",
            "tests/tool_rack/test_dummy.py": "# test\n",
        }
        for relative, text in required.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

        # A legacy engine file exists in the source tree but must never enter
        # the whitelisted shadow bundle.
        legacy = root / "engine" / "one_command_boundary_r2.py"
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.write_text("VENUE ORDER CODE", encoding="utf-8")
        return temp, root

    def test_bundle_contains_only_whitelisted_shadow_surfaces(self):
        temp, root = self.fixture()
        try:
            out = root / "bundle.zip"
            result = build(root, out)
            self.assertGreater(result["file_count"], 0)

            with zipfile.ZipFile(out, "r") as archive:
                names = set(archive.namelist())
                self.assertIn(
                    "TOOL_RACK_BUNDLE_MANIFEST.json",
                    names,
                )
                self.assertNotIn(
                    "engine/one_command_boundary_r2.py",
                    names,
                )
                manifest = json.loads(
                    archive.read(
                        "TOOL_RACK_BUNDLE_MANIFEST.json"
                    )
                )
                self.assertTrue(
                    manifest["read_only_strategy"]
                )
                self.assertEqual(
                    manifest["paper_execution_authority"],
                    "NONE",
                )
                self.assertEqual(
                    manifest["venue_order_authority"],
                    "NONE",
                )
                self.assertFalse(
                    manifest["contains_legacy_r22_engine"]
                )
        finally:
            temp.cleanup()


if __name__ == "__main__":
    unittest.main()
