from __future__ import annotations

import argparse
import json
from pathlib import Path

from strategy_core.shadow_compare import (
    compare_shadow_to_paper,
    load_paper_entries,
    load_shadow_event_journal,
    markdown_report,
)


def latest_paper_run(root: Path) -> Path:
    candidates = [
        path
        for path in root.glob("PAPER_*")
        if path.is_dir()
        and (path / "r20_verified_paper_trade_events.csv").is_file()
    ]
    if not candidates:
        raise FileNotFoundError(
            f"No PAPER run with canonical trade ledger found under {root}"
        )
    return max(
        candidates,
        key=lambda path: path.stat().st_mtime,
    )


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("run_dir",type=Path,nargs="?")
    parser.add_argument(
        "--runs-root",
        type=Path,
        default=Path(r"E:\TachyosR22IndependentPaperExperiments"),
    )
    parser.add_argument(
        "--shadow-root",
        type=Path,
        default=Path(r"E:\TachyosToolRackShadow"),
    )
    parser.add_argument("--before-seconds",type=float,default=120.0)
    parser.add_argument("--after-seconds",type=float,default=120.0)
    args=parser.parse_args()

    run=(args.run_dir or latest_paper_run(args.runs_root)).resolve()
    shadow=args.shadow_root/run.name
    event_path=shadow/"tool_rack_events.jsonl"
    status_path=shadow/"TOOL_RACK_SHADOW_STATUS.json"
    ledger_path=run/"r20_verified_paper_trade_events.csv"

    timeline=load_shadow_event_journal(event_path)
    status=(
        json.loads(
            status_path.read_text(
                encoding="utf-8"
            )
        )
        if status_path.is_file()
        else {}
    )
    entries=load_paper_entries(
        ledger_path,
        run_id=status.get("run_id"),
        session_id=status.get("session_id"),
    )
    report=compare_shadow_to_paper(
        timeline,
        entries,
        before_seconds=args.before_seconds,
        after_seconds=args.after_seconds,
    )

    shadow.mkdir(parents=True,exist_ok=True)
    json_path=shadow/"TOOL_RACK_SHADOW_VS_PAPER.json"
    md_path=shadow/"TOOL_RACK_SHADOW_VS_PAPER.md"
    json_path.write_text(
        json.dumps(report,indent=2,default=str),
        encoding="utf-8",
    )
    md_path.write_text(
        markdown_report(report),
        encoding="utf-8",
    )
    print(md_path)
    print(json.dumps(report["summary"],indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
