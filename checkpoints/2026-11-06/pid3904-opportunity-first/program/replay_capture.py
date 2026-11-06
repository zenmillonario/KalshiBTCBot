"""Replay a verified synchronous-engine input tape; no exchange connection."""
import argparse
import json
from pathlib import Path

from engine_replay import ReplayMismatch, replay
from bounded_tape import TapeError
from run_validation import network_forbidden


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tape", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True,
                        help="Parent of a new fresh run directory")
    parser.add_argument("--reference", type=Path,
                        help="Original engine output directory; enables exact full-file comparison")
    args = parser.parse_args()
    try:
        with network_forbidden():
            report = replay(args.tape, args.out, reference_dir=args.reference)
    except ReplayMismatch as exc:
        print(json.dumps({"pass": False, "first_divergence": exc.report}, indent=2))
        return 2
    except TapeError as exc:
        print(json.dumps({"pass": False, "invalid_evidence": str(exc)}, indent=2))
        return 3
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
