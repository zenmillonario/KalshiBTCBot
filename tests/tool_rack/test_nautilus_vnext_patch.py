import importlib.util
import tempfile
import unittest
from pathlib import Path


PATCH = (
    Path(__file__).resolve().parents[2]
    / "nautilus_vnext"
    / "APPLY_NAUTILUS_VNEXT.py"
)
spec = importlib.util.spec_from_file_location(
    "nautilus_vnext_patch",
    PATCH,
)
mod = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(mod)


class NautilusVNextPatchTests(unittest.TestCase):
    def fixture(self):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        (root / "static").mkdir()

        (root / "static/index.html").write_text(
            '<div class="identity-strip"><span id="runIdentity">'
            'Attaching to the selected run…</span><span id="sourceStatus">'
            'No trading authority</span></div>',
            encoding="utf-8",
        )
        (root / "static/chart.js").write_text(
            "this.ratio=.75",
            encoding="utf-8",
        )
        (root / "static/app.js").write_text(
            "const grid=(parent,items)=>{const g=el('div',null,'metric-grid'+"
            "(items.length===2?' two':''));\n"
            "grid(n,[['ENTRY',quote(p.entry_ask)],['NATIVE BID',"
            "finite(shownBid)?quote(shownBid):'—'],['CONTRACTS',"
            "price(p.remaining_qty??p.qty,0)]]);\n"
            "  function renderPositions(){\n"
            "renderTop();renderPositions();renderProtection();renderDetails();"
            "renderTable();renderFeed();\n"
            "if(state){renderTop();renderPositions();renderProtection();}",
            encoding="utf-8",
        )
        (root / "static/bridge.css").write_text(
            "body{}",
            encoding="utf-8",
        )
        (root / "adapter.py").write_text(
            'import math\nimport re\n'
            '    for field, source in (("mfe", "mfe_pct"), ("mae", "mae_pct")):\n'
            '        v = number(detail.get(source))\n'
            '        if v is not None:\n'
            '            out[field] = v\n'
            '    return out\n'
            '        observer = {}\n'
            '        if self.lab:\n'
            '                    market=market, quote=qout, candles=candles, emas=sorted(self.emas.values(), key=lambda e: e["time"]),\n'
            '                    targets=list(self.targets.values()), quotes=list(self.quotes), trades=trades, positions=positions,\n',
            encoding="utf-8",
        )
        return temp, root

    def test_patch_changes_expected_visual_and_readonly_surfaces(self):
        temp, root = self.fixture()
        try:
            mod.apply(root, verify_hashes=False)
            index = (root / "static/index.html").read_text()
            chart = (root / "static/chart.js").read_text()
            app = (root / "static/app.js").read_text()
            css = (root / "static/bridge.css").read_text()
            adapter = (root / "adapter.py").read_text()

            self.assertIn("toolRackStrip", index)
            self.assertIn("this.ratio=.83", chart)
            self.assertIn("MAX @ $1", app)
            self.assertIn("renderToolRack", app)
            self.assertIn("31fr", css)
            self.assertIn("max-height:190px", css)
            self.assertIn("maximum_roi_pct", adapter)
            self.assertIn("execution_authority", adapter)
            self.assertIn("TACHYOS_TOOL_RACK_SHADOW_ROOT", adapter)
        finally:
            temp.cleanup()

    def test_patch_is_idempotent(self):
        temp, root = self.fixture()
        try:
            mod.apply(root, verify_hashes=False)
            mod.apply(root, verify_hashes=False)
            css = (root / "static/bridge.css").read_text()
            index = (root / "static/index.html").read_text()
            self.assertEqual(css.count(mod.MARKER), 1)
            self.assertEqual(index.count("toolRackStrip"), 1)
        finally:
            temp.cleanup()


if __name__ == "__main__":
    unittest.main()
