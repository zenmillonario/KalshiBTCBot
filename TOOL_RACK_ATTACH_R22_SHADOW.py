from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from strategy_core.event_timeline import ShadowEventTimeline
from strategy_core.r22_run_source import R22RunShadowSource
from strategy_core.shadow_engine import ToolRackShadowEngine


def latest_paper_run(root: Path) -> Path:
    candidates = [
        path
        for path in root.glob("PAPER_*")
        if path.is_dir()
        and (path / "tachys_runtime_hf2.json").is_file()
        and (path / "tachys_ema_geometry_v9_4i.csv").is_file()
    ]
    if not candidates:
        raise FileNotFoundError(
            f"No R22 PAPER run with runtime + geometry found under {root}"
        )
    return max(
        candidates,
        key=lambda path: path.stat().st_mtime,
    )


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(payload, indent=2, default=str),
        encoding="utf-8",
    )
    os.replace(temp, path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Tachyos Tool Rack read-only sidecar for an existing R22 PAPER run"
        )
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        help="Exact existing PAPER run directory",
    )
    parser.add_argument(
        "--runs-root",
        type=Path,
        default=Path(r"E:\TachyosR22IndependentPaperExperiments"),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(r"E:\TachyosToolRackShadow"),
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
    )
    parser.add_argument(
        "--once",
        action="store_true",
    )
    args = parser.parse_args()

    run_dir = args.run_dir or latest_paper_run(args.runs_root)
    source = R22RunShadowSource(run_dir)
    engine = ToolRackShadowEngine()
    timeline = ShadowEventTimeline(max_events=300)

    output_dir = args.output_root / run_dir.name
    status_path = output_dir / "TOOL_RACK_SHADOW_STATUS.json"
    timeline_path = output_dir / "TOOL_RACK_SHADOW_TIMELINE.json"
    journal_path = output_dir / "tool_rack_shadow.jsonl"
    event_journal_path = output_dir / "tool_rack_events.jsonl"

    while True:
        try:
            state = source.read()
            result = engine.evaluate(state.frame)
            new_events = timeline.observe(
                ts=float(result["now_ts"]),
                ticker=str(result["ticker"]),
                result=result,
            )
            payload = {
                "schema": "TACHYOS_TOOL_RACK_SHADOW_V1",
                "read_only": True,
                "execution_authority": "NONE",
                "source_run_dir": str(run_dir),
                "run_id": state.run_id,
                "session_id": state.session_id,
                "geometry_rows_used": state.geometry_rows_used,
                "geometry_age_seconds": state.geometry_age_seconds,
                "source_files": state.source_files,
                "tool_rack": result,
                "recent_events": timeline.snapshot()[-24:],
            }
            timeline_payload = {
                "schema": "TACHYOS_TOOL_RACK_TIMELINE_V1",
                "read_only": True,
                "execution_authority": "NONE",
                "source_run_dir": str(run_dir),
                "run_id": state.run_id,
                "session_id": state.session_id,
                "events": timeline.snapshot(),
            }
        except Exception as exc:
            new_events = ()
            timeline_payload = {
                "schema": "TACHYOS_TOOL_RACK_TIMELINE_V1",
                "read_only": True,
                "execution_authority": "NONE",
                "source_run_dir": str(run_dir),
                "events": timeline.snapshot(),
            }
            payload = {
                "schema": "TACHYOS_TOOL_RACK_SHADOW_V1",
                "read_only": True,
                "execution_authority": "NONE",
                "source_run_dir": str(run_dir),
                "error": f"{type(exc).__name__}: {exc}",
            }

        atomic_json(status_path, payload)
        atomic_json(timeline_path, timeline_payload)
        output_dir.mkdir(parents=True, exist_ok=True)
        with journal_path.open(
            "a",
            encoding="utf-8",
        ) as handle:
            handle.write(
                json.dumps(
                    payload,
                    default=str,
                )
                + "\n"
            )

        if new_events:
            with event_journal_path.open(
                "a",
                encoding="utf-8",
            ) as handle:
                for event in new_events:
                    handle.write(
                        json.dumps(
                            event.as_dict(),
                            default=str,
                        )
                        + "\n"
                    )

        print(
            json.dumps(
                payload.get("tool_rack", payload),
                default=str,
            ),
            flush=True,
        )

        if args.once:
            return 0
        time.sleep(max(0.2, args.interval))


if __name__ == "__main__":
    raise SystemExit(main())
