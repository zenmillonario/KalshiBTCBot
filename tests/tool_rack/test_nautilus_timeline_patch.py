import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT=Path(__file__).resolve().parents[2]
BASE_PATH=ROOT/"nautilus_vnext"/"APPLY_NAUTILUS_VNEXT.py"
TIMELINE_PATH=ROOT/"nautilus_vnext"/"APPLY_TOOL_RACK_TIMELINE.py"


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod


base=load("nautilus_vnext_base",BASE_PATH)
timeline=load("nautilus_vnext_timeline",TIMELINE_PATH)


class NautilusTimelinePatchTests(unittest.TestCase):
    def fixture(self):
        temp=tempfile.TemporaryDirectory()
        root=Path(temp.name)
        (root/"static").mkdir()
        (root/"static/index.html").write_text(
            '<div class="identity-strip"><span id="runIdentity">'
            'Attaching to the selected run…</span><span id="sourceStatus">'
            'No trading authority</span></div>',
            encoding="utf-8",
        )
        (root/"static/chart.js").write_text("this.ratio=.75",encoding="utf-8")
        (root/"static/app.js").write_text(
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
        (root/"static/bridge.css").write_text("body{}",encoding="utf-8")
        (root/"adapter.py").write_text(
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
        base.apply(root,verify_hashes=False)
        return temp,root

    def test_timeline_extension_adds_readonly_timeline_surfaces(self):
        temp,root=self.fixture()
        try:
            timeline.apply(root)
            index=(root/"static/index.html").read_text()
            app=(root/"static/app.js").read_text()
            adapter=(root/"adapter.py").read_text()
            css=(root/"static/bridge.css").read_text()
            self.assertIn('id="toolRackTimeline"',index)
            self.assertIn("renderToolRackTimeline",app)
            self.assertIn("tool_rack_timeline",adapter)
            self.assertIn("TOOL_RACK_SHADOW_TIMELINE.json",adapter)
            self.assertIn("territory-release-transition",css)
            self.assertIn("marker-handoff",css)
            self.assertIn("paper-entry",css)
            self.assertIn("PAPER '+kind.toUpperCase()",app)
        finally:
            temp.cleanup()

    def test_timeline_extension_is_idempotent(self):
        temp,root=self.fixture()
        try:
            timeline.apply(root)
            timeline.apply(root)
            index=(root/"static/index.html").read_text()
            css=(root/"static/bridge.css").read_text()
            self.assertEqual(index.count('id="toolRackTimeline"'),1)
            self.assertEqual(css.count(timeline.MARKER),1)
        finally:
            temp.cleanup()


if __name__=="__main__":
    unittest.main()
