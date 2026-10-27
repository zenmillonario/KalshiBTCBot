from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path


ALLOWED_ROOT_FILES = {
    "CHECK_TOOL_RACK_V1.py",
    "00_CHECK_TOOL_RACK_SHADOW.cmd",
    "START_TOOL_RACK_SHADOW.cmd",
    "TOOL_RACK_ATTACH_R22_SHADOW.py",
    "TOOL_RACK_SHADOW_REPLAY.py",
    "TOOL_RACK_COMPARE_SHADOW_TO_PAPER.py",
    "02_COMPARE_SHADOW_TO_PAPER.cmd",
    "README_TOOL_RACK_SHADOW.md",
}

ALLOWED_PREFIXES = (
    "strategy_core/",
    "tests/tool_rack/",
    "nautilus_vnext/",
    "docs/TOOL_RACK_",
)

FORBIDDEN_FRAGMENTS = (
    "/engine/",
    "engine/",
    "one_command_boundary",
    "r8_streaming_dispatcher",
    "r17_guarded_paper_cutover",
    "kalshi_order",
    "create_order",
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def allowed(relative: str) -> bool:
    normalized = relative.replace("\\", "/")
    if normalized == "tests/tool_rack/test_shadow_bundle.py":
        return False
    if normalized in ALLOWED_ROOT_FILES:
        return True
    return any(normalized.startswith(prefix) for prefix in ALLOWED_PREFIXES)


def collect(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if allowed(relative):
            files.append(path)
    return sorted(files)


def validate_whitelist(root: Path, files: list[Path]) -> None:
    if not files:
        raise RuntimeError("Tool Rack bundle whitelist selected no files")

    required = {
        "CHECK_TOOL_RACK_V1.py",
        "00_CHECK_TOOL_RACK_SHADOW.cmd",
        "START_TOOL_RACK_SHADOW.cmd",
        "TOOL_RACK_ATTACH_R22_SHADOW.py",
        "TOOL_RACK_COMPARE_SHADOW_TO_PAPER.py",
        "02_COMPARE_SHADOW_TO_PAPER.cmd",
        "README_TOOL_RACK_SHADOW.md",
        "strategy_core/tool_rack.py",
        "strategy_core/commander.py",
        "strategy_core/r22_run_source.py",
        "nautilus_vnext/APPLY_NAUTILUS_VNEXT.py",
        "nautilus_vnext/APPLY_TOOL_RACK_TIMELINE.py",
        "docs/TOOL_RACK_PHASE2_STATUS.md",
    }
    selected = {
        path.relative_to(root).as_posix()
        for path in files
    }
    missing = sorted(required - selected)
    if missing:
        raise RuntimeError(
            "Tool Rack bundle missing required files: "
            + ", ".join(missing)
        )

    forbidden = []
    for relative in selected:
        low = relative.lower()
        if any(fragment.lower() in low for fragment in FORBIDDEN_FRAGMENTS):
            forbidden.append(relative)
    if forbidden:
        raise RuntimeError(
            "Forbidden execution/legacy files entered shadow bundle: "
            + ", ".join(sorted(forbidden))
        )


def build(root: Path, output: Path) -> dict:
    files = collect(root)
    validate_whitelist(root, files)

    manifest_files = {}
    payloads: list[tuple[str, bytes]] = []

    for path in files:
        relative = path.relative_to(root).as_posix()
        data = path.read_bytes()
        payloads.append((relative, data))
        manifest_files[relative] = {
            "sha256": sha256_bytes(data),
            "size": len(data),
        }

    manifest = {
        "schema": "TACHYOS_TOOL_RACK_SHADOW_BUNDLE_V1",
        "read_only_strategy": True,
        "paper_execution_authority": "NONE",
        "venue_order_authority": "NONE",
        "contains_legacy_r22_engine": False,
        "files": manifest_files,
    }
    manifest_bytes = json.dumps(
        manifest,
        indent=2,
        sort_keys=True,
    ).encode("utf-8")

    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        output,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for relative, data in payloads:
            archive.writestr(relative, data)
        archive.writestr(
            "TOOL_RACK_BUNDLE_MANIFEST.json",
            manifest_bytes,
        )

    with zipfile.ZipFile(output, "r") as archive:
        bad = archive.testzip()
        if bad is not None:
            raise RuntimeError(
                f"ZIP integrity failure at {bad}"
            )

    return {
        "output": str(output),
        "file_count": len(payloads),
        "zip_sha256": hashlib.sha256(
            output.read_bytes()
        ).hexdigest(),
        "manifest_sha256": sha256_bytes(
            manifest_bytes
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("TACHYOS_TOOL_RACK_V1_SHADOW_VALIDATION.zip"),
    )
    args = parser.parse_args()
    result = build(
        args.root.resolve(),
        args.output.resolve(),
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
