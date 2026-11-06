from __future__ import annotations
import json
from pathlib import Path

CORPUS = Path(__file__).with_name("docs") / "PID13560_POSITIVE_CONTROL_CORPUS.json"

ALLOWED = {
    "HEIST_OUTER_EDGE_TACTICAL_RENTER",
    "HEIST_PARALLEL_STALLED_EDGE_RETURN",
    "COMMANDER_RECENT_LEVEL_MATCH_SUB20_RETURN",
    "COMMANDER_INHERITED_YOUNG_LEG_ROLLOVER_CONTINUATION",
    "COMMANDER_EXTENDED_MOUNTAIN_NEW_EXTREME_SUB20_RETURN",
}

def main() -> int:
    data=json.loads(CORPUS.read_text(encoding="utf-8"))
    rows=[]
    controls=data.get("controls") or []
    rows.append(("eight_frozen_positive_controls", len(controls)==8, f"count={len(controls)}"))
    seen=set()
    for c in controls:
        name=f"trade_{c['trade']}_{c['setup']}"
        reason=c.get("reason")
        entry=float(c.get("entry") or 0)
        mfe=float(c.get("mfe_bid") or 0)
        roi=float(c.get("mfe_roi") or -1)
        ok=(reason in ALLOWED and c.get("side") in {"YES","NO"} and 0 < entry <= 1
            and entry <= mfe <= 1 and roi >= .80 and abs((mfe/entry-1)-roi) < 1e-6
            and c.get("lesson"))
        rows.append((name, bool(ok), f"{reason} {entry:.4f}->{mfe:.4f} roi={roi:.3f}"))
        seen.add(reason)
    rows.append(("covers_level_match_both_sides", sum(c["reason"]=="COMMANDER_RECENT_LEVEL_MATCH_SUB20_RETURN" for c in controls)>=3
                 and {c["side"] for c in controls if c["reason"]=="COMMANDER_RECENT_LEVEL_MATCH_SUB20_RETURN"}=={"YES","NO"}, "level-match mirror"))
    rows.append(("covers_rollover_and_extreme_and_heist", {
        "COMMANDER_INHERITED_YOUNG_LEG_ROLLOVER_CONTINUATION",
        "COMMANDER_EXTENDED_MOUNTAIN_NEW_EXTREME_SUB20_RETURN",
        "HEIST_OUTER_EDGE_TACTICAL_RENTER",
        "HEIST_PARALLEL_STALLED_EDGE_RETURN",
    }.issubset(seen), "families present"))
    passed=sum(ok for _,ok,_ in rows)
    print(f"PID13560 POSITIVE CONTROL CONSTRUCT: {passed}/{len(rows)} PASS")
    for name,ok,detail in rows:
        print(("PASS" if ok else "FAIL"), name, detail)
    return 0 if passed==len(rows) else 1

if __name__ == "__main__":
    raise SystemExit(main())
