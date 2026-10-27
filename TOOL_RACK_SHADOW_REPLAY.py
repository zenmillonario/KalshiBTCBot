from __future__ import annotations

import argparse
import json
from pathlib import Path

from strategy_core.shadow_engine import (
    ToolRackShadowEngine,
)
from strategy_core.shadow_frame import ShadowFrame


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only Tachyos Tool Rack JSONL replay"
        )
    )
    parser.add_argument(
        "input_jsonl",
        type=Path,
    )
    parser.add_argument(
        "output_jsonl",
        type=Path,
    )
    args = parser.parse_args()

    engine = ToolRackShadowEngine()
    with (
        args.input_jsonl.open(
            "r",
            encoding="utf-8",
        ) as src,
        args.output_jsonl.open(
            "w",
            encoding="utf-8",
        ) as dst,
    ):
        for line in src:
            line = line.strip()
            if not line:
                continue
            frame = ShadowFrame.from_mapping(
                json.loads(line)
            )
            dst.write(
                json.dumps(
                    engine.evaluate(frame),
                    default=str,
                )
                + "\n"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
