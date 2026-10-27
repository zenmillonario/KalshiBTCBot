"""Export a stopped Tool Rack PAPER run with a verified economic journal."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import zipfile

from TOOL_RACK_PAPER import default_output_root
from strategy_core.paper_execution import PaperExecutioner


def export_run(run: Path, output: Path | None = None) -> Path:
    run = run.expanduser().resolve()
    status = json.loads((run / "STATUS.json").read_text(encoding="utf-8"))
    if status.get("state") != "STOPPED":
        raise ValueError("Stop the PAPER run before making its final diagnostic archive.")
    checked = PaperExecutioner.inspect_journal(run)
    if not checked["records"] or checked["state"] is None:
        raise ValueError("A committed PAPER journal is required for a verified export.")
    allowed = {"RUN_MANIFEST.json", "RUN_SUMMARY.json", "STATUS.json", "PAPER_LEDGER.json",
               "ERROR.json", "decisions.jsonl", "physical_geometry.jsonl", "market_data_source.jsonl",
               "console.log"}
    paths = sorted([p for p in run.iterdir() if p.is_file() and p.name in allowed] +
                   list((run / "paper_journal").glob("*.json")))
    if output is None:
        output = run.parent / (run.name + "_DIAGNOSTICS.zip")
    output = output.expanduser().resolve()
    if output.exists():
        raise FileExistsError("Choose another archive path; an existing diagnostic archive is never replaced.")
    manifest = {"mode": "PAPER", "run_id": run.name,
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "journal_verified": True, "journal_seq": checked["seq"],
                "journal_sha256": checked["sha256"],
                "files": {p.relative_to(run).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "x", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in paths:
            archive.write(path, f"{run.name}/{path.relative_to(run).as_posix()}")
        archive.writestr(f"{run.name}/EXPORT_MANIFEST.json", json.dumps(manifest, indent=2, sort_keys=True))
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--output-root", type=Path, default=default_output_root())
    args = parser.parse_args(argv)
    if args.run is None:
        latest = json.loads((args.output_root / "LAST_RUN.json").read_text(encoding="utf-8"))
        args.run = Path(latest["run_dir"])
    print(export_run(args.run, args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
