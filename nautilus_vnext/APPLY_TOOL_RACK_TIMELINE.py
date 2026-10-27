from __future__ import annotations

import argparse
from pathlib import Path


MARKER = "Tool Rack territory timeline ribbon v1"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"{label}: expected exactly one source pattern, found {count}"
        )
    return text.replace(old, new, 1)


def patch_index(root: Path) -> None:
    path = root / "static/index.html"
    text = path.read_text(encoding="utf-8")
    if 'id="toolRackTimeline"' in text:
        return
    key = 'id="toolRackStrip"'
    at = text.find(key)
    if at < 0:
        raise RuntimeError("Nautilus vNext Tool Rack strip not found")
    close = text.find("</div>", at)
    if close < 0:
        raise RuntimeError("Nautilus vNext Tool Rack strip closing div not found")
    close += len("</div>")
    insertion = """
<div id="toolRackTimeline" class="tool-rack-timeline hidden" aria-label="Tool Rack shadow territory timeline"></div>"""
    text = text[:close] + insertion + text[close:]
    path.write_text(text, encoding="utf-8")


def patch_adapter(root: Path) -> None:
    path = root / "adapter.py"
    text = path.read_text(encoding="utf-8")

    text = replace_once(
        text,
        "        tool_rack = {}\n        try:\n",
        "        tool_rack = {}\n        tool_rack_timeline = []\n        try:\n",
        "timeline adapter init",
    )

    anchor = '                tool_rack = shadow.get("tool_rack") or {}\n'
    addition = anchor + '''                timeline_path = shadow_root / self.run.name / "TOOL_RACK_SHADOW_TIMELINE.json"
                timeline = json_file(timeline_path, 4_000_000) if timeline_path.is_file() else {}
                timeline_run = basename(str(timeline.get("source_run_dir") or "")) if timeline else ""
                if (timeline and timeline.get("read_only") is True and
                        timeline.get("execution_authority") == "NONE" and
                        timeline_run == self.run.name and isinstance(timeline.get("events"), list)):
                    tool_rack_timeline = timeline.get("events")[-300:]
'''
    text = replace_once(
        text,
        anchor,
        addition,
        "timeline adapter source",
    )

    text = replace_once(
        text,
        "                    tool_rack=tool_rack,\n",
        "                    tool_rack=tool_rack,\n                    tool_rack_timeline=tool_rack_timeline,\n",
        "timeline snapshot field",
    )

    path.write_text(text, encoding="utf-8")


TIMELINE_JS = r'''  function renderToolRackTimeline(){
    const host=$('toolRackTimeline');if(!host)return;
    const events=Array.isArray(state?.tool_rack_timeline)?state.tool_rack_timeline:[];
    const timed=events.filter(e=>finite(Number(e?.ts))).sort((a,b)=>Number(a.ts)-Number(b.ts));
    const territory=timed.filter(e=>e.event_type==='TERRITORY'&&e.territory);
    if(!territory.length){host.classList.add('hidden');host.innerHTML='';return;}
    host.classList.remove('hidden');host.innerHTML='';

    const latest=Math.max(Number(timed[timed.length-1]?.ts)||0,Number(territory[territory.length-1]?.ts)||0);
    const span=2700,start=latest-span;
    let prior=null;
    for(const e of territory){if(Number(e.ts)<=start)prior=e;else break;}
    const chapters=[];
    if(prior)chapters.push({...prior,ts:start});
    for(const e of territory){if(Number(e.ts)>start)chapters.push(e);}
    if(!chapters.length)chapters.push({...territory[territory.length-1],ts:start});

    const label=document.createElement('span');
    label.className='territory-ribbon-label';
    label.textContent='SHADOW / PAPER 45M';
    host.appendChild(label);

    const track=document.createElement('div');
    track.className='territory-ribbon-track';
    host.appendChild(track);

    const cls=v=>'territory-'+String(v||'unknown').toLowerCase().replaceAll('_','-');
    chapters.forEach((e,i)=>{
      const a=Math.max(start,Number(e.ts)||start);
      const b=Math.min(latest,i+1<chapters.length?Number(chapters[i+1].ts):latest);
      if(b<=a)return;
      const seg=document.createElement('div');
      seg.className='territory-ribbon-segment '+cls(e.territory);
      seg.style.left=((a-start)/span*100)+'%';
      seg.style.width=(Math.max(0.35,(b-a)/span*100))+'%';
      seg.title=readable(e.territory)+(e.side?' · '+e.side:'')+' · '+new Date(a*1000).toLocaleTimeString();
      const dur=b-a;
      if(dur>=90)seg.textContent=readable(e.territory).replace('ALTERNATING ','ALT ');
      track.appendChild(seg);
    });

    const markerEvents=timed.filter(e=>{
      if(Number(e.ts)<start||Number(e.ts)>latest)return false;
      if(e.event_type==='HANDOFF')return true;
      return e.event_type==='INTENT'&&['ENTER','RELAY'].includes(e.action);
    });
    markerEvents.forEach(e=>{
      const marker=document.createElement('span');
      const kind=e.event_type==='HANDOFF'?'handoff':String(e.action||'').toLowerCase();
      marker.className='territory-ribbon-marker marker-'+kind;
      marker.style.left=((Number(e.ts)-start)/span*100)+'%';
      marker.textContent=kind==='enter'?'●':'◆';
      marker.title=(e.event_type==='HANDOFF'?'HANDOFF':String(e.action||''))+
        (e.accepted_side?' '+e.accepted_side:'')+
        (finite(e.observed_ask)?' · '+quote(e.observed_ask):'')+
        (e.reason?' · '+readable(e.reason):'');
      track.appendChild(marker);
    });

    const paperTrades=Array.isArray(state?.trades)?state.trades:[];
    paperTrades.forEach(t=>{
      [
        ['entry',t.entry_ts,t.entry_ask,'▲'],
        ['exit',t.exit_ts,t.exit_bid,'○']
      ].forEach(([kind,ts,px,symbol])=>{
        if(!finite(ts)||Number(ts)<start||Number(ts)>latest)return;
        const marker=document.createElement('span');
        marker.className='territory-ribbon-marker paper-'+kind;
        marker.style.left=((Number(ts)-start)/span*100)+'%';
        marker.textContent=symbol;
        marker.title='PAPER '+kind.toUpperCase()+' #'+t.trade_id+' '+t.side+
          (finite(px)?' · '+quote(px):'');
        track.appendChild(marker);
      });
    });
  }
'''


def patch_app(root: Path) -> None:
    path = root / "static/app.js"
    text = path.read_text(encoding="utf-8")
    if "function renderToolRackTimeline()" not in text:
        text = replace_once(
            text,
            "  function renderPositions(){\n",
            TIMELINE_JS + "  function renderPositions(){\n",
            "timeline renderer",
        )

    text = text.replace(
        "renderTop();renderToolRack();renderPositions();renderProtection();renderDetails();renderTable();renderFeed();",
        "renderTop();renderToolRack();renderToolRackTimeline();renderPositions();renderProtection();renderDetails();renderTable();renderFeed();",
    )
    text = text.replace(
        "if(state){renderTop();renderToolRack();renderPositions();renderProtection();}",
        "if(state){renderTop();renderToolRack();renderToolRackTimeline();renderPositions();renderProtection();}",
    )
    path.write_text(text, encoding="utf-8")


CSS = r'''
/* Tool Rack territory timeline ribbon v1 — shadow/read-only. */
.tool-rack-timeline{
  flex:0 0 auto;display:grid;grid-template-columns:78px minmax(0,1fr);align-items:center;gap:8px;
  margin:-2px var(--gutter) 7px;padding:3px 9px;border:1px solid #1a3442;border-radius:5px;background:#07131b;
  min-height:25px;
}
.territory-ribbon-label{font-size:7.5px;letter-spacing:.55px;color:#5d7b8b;white-space:nowrap}
.territory-ribbon-track{position:relative;height:16px;border-radius:3px;overflow:visible;background:#091923;border:1px solid #17303d}
.territory-ribbon-segment{position:absolute;top:0;height:100%;overflow:hidden;padding:1px 5px;font-size:7.5px;line-height:13px;white-space:nowrap;text-overflow:ellipsis;color:#c9dce4;border-right:1px solid rgba(255,255,255,.12)}
.territory-up-rail{background:#123e37}
.territory-down-rail{background:#17364e}
.territory-alternating-mountain{background:#4a3820}
.territory-market-heist{background:#392d4c}
.territory-release-transition{background:#573126}
.territory-rolling-mountain{background:#34414a}
.territory-unknown,.territory-compression-unresolved{background:#263139}
.territory-ribbon-marker{position:absolute;top:-4px;transform:translateX(-50%);z-index:4;font-size:10px;line-height:10px;text-shadow:0 0 4px #000;cursor:help}
.marker-enter{color:#78d8ff}
.marker-relay{color:#f5c56d}
.marker-handoff{color:#ff936d}
.paper-entry{color:#ffffff;top:8px;font-size:9px}
.paper-exit{color:#a5bbc7;top:8px;font-size:9px}
'''


def patch_css(root: Path) -> None:
    path = root / "static/bridge.css"
    text = path.read_text(encoding="utf-8")
    if MARKER not in text:
        text += "\n\n" + CSS.strip() + "\n"
    path.write_text(text, encoding="utf-8")


def apply(root: Path) -> None:
    patch_index(root)
    patch_adapter(root)
    patch_app(root)
    patch_css(root)


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("nautilus_root",type=Path)
    args=parser.parse_args()
    apply(args.nautilus_root)
    print("Nautilus Tool Rack timeline patch applied")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
