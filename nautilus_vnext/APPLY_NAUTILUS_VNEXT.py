from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


BASE_HASHES = {
    "static/bridge.css": "319df6d1ef02f7e96854d59a2a16ac8dccb70f7f90dbb1209f8b936108bf23b8",
    "static/chart.js": "a62f9a0f6dd2ed1a363ba73c7aa78074bdb39a5aa9d2690a5ac9dcd895c40a82",
    "static/app.js": "2b1ad96cc52832b4789bf09fddb7f1d58e238e25d2d40af44c71d70a8247ca64",
    "adapter.py": "8b7735773bfb58868c0c44cd3a959cf62ade1223e072e01045250b29bcb4a096",
    "static/index.html": "0a9bc18d5bc776b43489c10cff7119fc93d36b0e192b38f52c3627dd055f887f",
}

MARKER = "Tool Rack / TradingView proportion pass vNext"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"{label}: expected exactly one source pattern, found {count}"
        )
    return text.replace(old, new, 1)


def verify_base(root: Path) -> None:
    mismatches = []
    for relative, expected in BASE_HASHES.items():
        path = root / relative
        actual = sha256(path) if path.is_file() else "MISSING"
        if actual != expected:
            mismatches.append(
                f"{relative}: expected {expected}, got {actual}"
            )
    if mismatches:
        raise RuntimeError(
            "Nautilus vNext known-base verification failed:\n"
            + "\n".join(mismatches)
        )


def patch_index(root: Path) -> None:
    path = root / "static/index.html"
    text = path.read_text(encoding="utf-8")
    old = (
        '<div class="identity-strip"><span id="runIdentity">'
        'Attaching to the selected run…</span><span id="sourceStatus">'
        'No trading authority</span></div>'
    )
    new = old + """
<div id="toolRackStrip" class="tool-rack-strip hidden" aria-label="Tool Rack shadow strategy status"><span><b>TERRITORY</b> <strong id="toolRackTerritory">—</strong></span><span><b>PRIMARY</b> <strong id="toolRackPrimary">—</strong></span><span><b>OVERLAY</b> <strong id="toolRackOverlay">—</strong></span><span><b>INTENT</b> <strong id="toolRackIntent">—</strong></span><span class="tool-rack-reason" id="toolRackReason">Shadow sidecar unavailable</span></div>"""
    path.write_text(
        replace_once(text, old, new, "index Tool Rack strip"),
        encoding="utf-8",
    )


def patch_chart(root: Path) -> None:
    path = root / "static/chart.js"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "this.ratio=.75",
        "this.ratio=.83",
        "chart price-pane ratio",
    )
    path.write_text(text, encoding="utf-8")


def patch_adapter(root: Path) -> None:
    path = root / "adapter.py"
    text = path.read_text(encoding="utf-8")

    text = replace_once(
        text,
        "import math\nimport re",
        "import math\nimport os\nimport re",
        "adapter os import",
    )

    old = '''    for field, source in (("mfe", "mfe_pct"), ("mae", "mae_pct")):
        v = number(detail.get(source))
        if v is not None:
            out[field] = v
    return out
'''
    new = '''    for field, source in (("mfe", "mfe_pct"), ("mae", "mae_pct")):
        v = number(detail.get(source))
        if v is not None:
            out[field] = v
    payoff = detail.get("payoff_capacity") or {}
    if isinstance(payoff, dict):
        out["maximum_roi_pct"] = number(payoff.get("maximum_roi_pct"))
        out["maximum_gross_profit"] = number(payoff.get("maximum_gross_profit"))
        out["remaining_gross_upside"] = number(payoff.get("remaining_gross_upside"))
        out["potential_fraction_reached"] = number(payoff.get("potential_fraction_reached"))
    return out
'''
    text = replace_once(text, old, new, "adapter payoff capacity")

    old = "        observer = {}\n        if self.lab:\n"
    new = '''        tool_rack = {}
        try:
            env_root = os.environ.get("TACHYOS_TOOL_RACK_SHADOW_ROOT")
            shadow_root = Path(env_root) if env_root else self.run.parent.parent / "TachyosToolRackShadow"
            shadow_path = shadow_root / self.run.name / "TOOL_RACK_SHADOW_STATUS.json"
            shadow = json_file(shadow_path, 1_000_000) if shadow_path.is_file() else {}
            source_run = basename(str(shadow.get("source_run_dir") or "")) if shadow else ""
            if (shadow and shadow.get("read_only") is True and
                    shadow.get("execution_authority") == "NONE" and
                    source_run == self.run.name and isinstance(shadow.get("tool_rack"), dict)):
                tool_rack = shadow.get("tool_rack") or {}
            elif shadow:
                self.errors.append("Tool Rack shadow identity/authority not confirmed; status withheld")
        except (OSError, ValueError, TypeError):
            self.errors.append("Tool Rack optional shadow status temporarily unavailable")
        observer = {}
        if self.lab:
'''
    text = replace_once(text, old, new, "adapter Tool Rack status")

    old = '''                    market=market, quote=qout, candles=candles, emas=sorted(self.emas.values(), key=lambda e: e["time"]),
                    targets=list(self.targets.values()), quotes=list(self.quotes), trades=trades, positions=positions,
'''
    new = '''                    market=market, quote=qout, candles=candles, emas=sorted(self.emas.values(), key=lambda e: e["time"]),
                    targets=list(self.targets.values()), quotes=list(self.quotes), trades=trades, positions=positions,
                    tool_rack=tool_rack,
'''
    text = replace_once(text, old, new, "adapter snapshot Tool Rack field")
    path.write_text(text, encoding="utf-8")


def patch_app(root: Path) -> None:
    path = root / "static/app.js"
    text = path.read_text(encoding="utf-8")

    text = replace_once(
        text,
        "const grid=(parent,items)=>{const g=el('div',null,'metric-grid'+(items.length===2?' two':''));",
        "const grid=(parent,items)=>{const g=el('div',null,'metric-grid'+(items.length===2?' two':items.length===4?' four':''));",
        "app four-column metric grid",
    )

    old = "grid(n,[['ENTRY',quote(p.entry_ask)],['NATIVE BID',finite(shownBid)?quote(shownBid):'—'],['CONTRACTS',price(p.remaining_qty??p.qty,0)]]);"
    new = "const maxWin=(finite(p.maximum_roi_pct)||finite(p.maximum_gross_profit))?pct(p.maximum_roi_pct)+' · '+money(p.maximum_gross_profit):'—';\n      grid(n,[['ENTRY',quote(p.entry_ask)],['NATIVE BID',finite(shownBid)?quote(shownBid):'—'],['CONTRACTS',price(p.remaining_qty??p.qty,0)],['MAX @ $1',maxWin]]);"
    text = replace_once(text, old, new, "app $1 upside metric")

    old = "  function renderPositions(){\n"
    new = '''  function renderToolRack(){
    const strip=$('toolRackStrip');if(!strip)return;const tr=state?.tool_rack;
    if(!tr||!tr.owned_territory){strip.classList.add('hidden');return;}
    strip.classList.remove('hidden');
    $('toolRackTerritory').textContent=readable(tr.owned_territory)+(tr.owned_side?' · '+tr.owned_side:'');
    $('toolRackPrimary').textContent=readable(tr.active_tool||'NONE');
    $('toolRackOverlay').textContent=(tr.active_overlays||[]).join(' + ')||'NONE';
    const action=tr.commander_action||'WAIT',side=tr.accepted_side?' '+tr.accepted_side:'';
    $('toolRackIntent').textContent=action+side;
    $('toolRackReason').textContent=readable(tr.commander_reason||tr.lane_resolution_reason||tr.ownership_reason);
  }
  function renderPositions(){
'''
    text = replace_once(text, old, new, "app Tool Rack renderer")

    text = text.replace(
        "renderTop();renderPositions();renderProtection();renderDetails();renderTable();renderFeed();",
        "renderTop();renderToolRack();renderPositions();renderProtection();renderDetails();renderTable();renderFeed();",
    )
    text = text.replace(
        "if(state){renderTop();renderPositions();renderProtection();}",
        "if(state){renderTop();renderToolRack();renderPositions();renderProtection();}",
    )
    path.write_text(text, encoding="utf-8")


CSS = r'''
/* Tool Rack / TradingView proportion pass vNext. Visual-only. */
body[data-layout="bridge"] .workspace{
  grid-template-columns:minmax(390px,31fr) minmax(520px,47fr) minmax(285px,22fr);
}
body[data-layout="desktop"] .workspace{
  grid-template-columns:minmax(350px,31fr) minmax(480px,48fr) minmax(270px,21fr);
}
body:is([data-layout="bridge"],[data-layout="desktop"]) .engine-feed{
  font-size:calc(12px * var(--type-scale));line-height:1.55;
}
body:is([data-layout="bridge"],[data-layout="desktop"]) .chart-toolbar{padding-top:5px;padding-bottom:5px}
body:is([data-layout="bridge"],[data-layout="desktop"]) .chart-legend{padding-top:4px;padding-bottom:4px}
body:is([data-layout="bridge"],[data-layout="desktop"]) .history-status{padding-top:2px;padding-bottom:3px}
body:is([data-layout="bridge"],[data-layout="desktop"]) .chart-foot{min-height:21px;padding-top:1px;padding-bottom:1px}
body:is([data-layout="bridge"],[data-layout="desktop"]) #positionsPanel{
  max-height:190px;min-height:0;overflow:hidden;
}
body:is([data-layout="bridge"],[data-layout="desktop"]) #positionsPanel .panel-heading{min-height:34px;height:34px}
body:is([data-layout="bridge"],[data-layout="desktop"]) #positionsPanel .card-body{padding:6px 9px}
body:is([data-layout="bridge"],[data-layout="desktop"]) #positionsPanel .position-header{margin-bottom:3px}
body:is([data-layout="bridge"],[data-layout="desktop"]) #positionsPanel .position-value{font-size:calc(19px * var(--type-scale));line-height:1.15}
body:is([data-layout="bridge"],[data-layout="desktop"]) #positionsPanel .metric-grid{margin:5px 0;gap:4px}
body:is([data-layout="bridge"],[data-layout="desktop"]) #positionsPanel .metric-grid.four{grid-template-columns:repeat(4,minmax(0,1fr))}
body:is([data-layout="bridge"],[data-layout="desktop"]) #positionsPanel .metric-grid label{font-size:calc(7.5px * var(--type-scale));margin-bottom:2px;white-space:nowrap}
body:is([data-layout="bridge"],[data-layout="desktop"]) #positionsPanel .metric-grid strong{font-size:calc(11px * var(--type-scale));white-space:nowrap}
body:is([data-layout="bridge"],[data-layout="desktop"]) #positionsPanel .context-note,
body:is([data-layout="bridge"],[data-layout="desktop"]) #positionsPanel .warning-note{font-size:calc(8px * var(--type-scale));line-height:1.25;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
body:is([data-layout="bridge"],[data-layout="desktop"]) #positionsPanel .side-label{font-size:calc(14px * var(--type-scale))}
body:is([data-layout="bridge"],[data-layout="desktop"]) #positionsPanel button{padding:4px 7px;min-height:26px;font-size:9px}
.tool-rack-strip{
  flex:0 0 auto;display:grid;grid-template-columns:auto auto auto auto minmax(160px,1fr);gap:6px 14px;align-items:center;
  margin:0 var(--gutter) 7px;padding:6px 10px;border:1px solid #24495b;border-radius:6px;background:linear-gradient(90deg,#0a1d29,#0a1721);
  font-size:calc(9px * var(--type-scale));color:#7598aa;min-height:31px;
}
.tool-rack-strip b{font-size:.82em;letter-spacing:.65px;color:#5f8092;margin-right:4px}
.tool-rack-strip strong{font-weight:600;color:#d0e8f1;white-space:nowrap}
.tool-rack-strip span:first-child strong{color:var(--cyan)}
.tool-rack-strip .tool-rack-reason{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;text-align:right;color:#9db2be}
@media(max-width:1399px){.tool-rack-strip{grid-template-columns:repeat(4,auto) minmax(100px,1fr);gap:5px 8px;font-size:9px}}
'''


def patch_bridge_css(root: Path) -> None:
    path = root / "static/bridge.css"
    text = path.read_text(encoding="utf-8")
    if MARKER not in text:
        text += "\n\n" + CSS.strip() + "\n"
    path.write_text(text, encoding="utf-8")


def apply(root: Path, verify_hashes: bool = True) -> None:
    if verify_hashes:
        verify_base(root)
    patch_index(root)
    patch_chart(root)
    patch_adapter(root)
    patch_app(root)
    patch_bridge_css(root)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("nautilus_root", type=Path)
    parser.add_argument(
        "--allow-source-drift",
        action="store_true",
        help="Skip known HF15 source hashes. Intended only for controlled porting.",
    )
    args = parser.parse_args()
    apply(
        args.nautilus_root,
        verify_hashes=not args.allow_source_drift,
    )
    print("Nautilus vNext patch applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
