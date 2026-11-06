"""Offline, bounded Looking Glass Construct. No feed, venue or trading runtime.

The ordinary portable gate needs Python only. Development/release verification
adds --with-js to execute the actual shipped chart/app code with Node adapters;
that mode fails if Node or either JavaScript check is unavailable.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parent
MODULES = (
    "tests.tool_rack.test_looking_glass_patterns",
    "tests.tool_rack.test_looking_glass",
    "tests.tool_rack.test_looking_glass_projection",
    "tests.tool_rack.test_nautilus_projection",
    "tests.tool_rack.test_nautilus_chart_source",
)
SOURCES = (
    "strategy_core/looking_glass.py", "strategy_core/nautilus_projection.py",
    "strategy_core/nautilus/chart.js", "strategy_core/nautilus/app.js",
    "strategy_core/nautilus/index.html", "strategy_core/nautilus/bridge.css",
    "strategy_core/nautilus/PROVENANCE.json",
)
JAVASCRIPT = (
    "tests/tool_rack/test_nautilus_looking_glass.js",
    "tests/tool_rack/test_nautilus_pattern_paths.js",
)


def ids(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from ids(item)
        else:
            yield item.id()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--with-js", action="store_true", help="Require Node and both actual-chart/app JavaScript checks")
    parser.add_argument("--output", type=Path, default=ROOT / "PID10656_LOOKING_GLASS_CONSTRUCT")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    suite = unittest.defaultTestLoader.loadTestsFromNames(MODULES)
    test_ids = list(ids(suite))
    log = io.StringIO()
    result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    (args.output / "python_checks.txt").write_text(log.getvalue(), encoding="utf-8")
    report = {"construct": "PID10656_LOOKING_GLASS", "passed": result.wasSuccessful(),
        "python_passed": result.wasSuccessful(), "python_test_count": result.testsRun,
        "python_check_count": result.testsRun, "python_test_ids": test_ids,
        "python_failures": len(result.failures), "python_errors": len(result.errors),
        "javascript": {"status": "NOT_REQUESTED", "requires_node_for_development_gate": True},
        "source_hashes": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in SOURCES},
        "authority": "READ_ONLY_OFFLINE_DISPLAY_CONSTRUCT",
        "future_input_used": False, "live_feed_started": False, "trade_runtime_started": False,
        "browser_layout_verified": False,
        "limitations": ["Synthetic positive/negative controls do not establish prediction accuracy.",
            "As-issued display samples are process-local, not a durable research journal.",
            "JavaScript adapters verify actual chart/app behavior, not full browser layout."]}
    if args.with_js:
        node = shutil.which("node")
        checks = []
        environment = dict(os.environ, NAUTILUS_TEST_PYTHON=sys.executable)
        for name in JAVASCRIPT:
            if not node or not (ROOT / name).is_file():
                checks.append({"path": name, "passed": False, "reason": "NODE_OR_CHECK_UNAVAILABLE"})
                continue
            try:
                executed = subprocess.run([node, str(ROOT / name)], cwd=ROOT, env=environment,
                    capture_output=True, text=True, timeout=60)
                (args.output / (Path(name).stem + ".txt")).write_text(executed.stdout + executed.stderr, encoding="utf-8")
                check = {"path": name, "passed": executed.returncode == 0, "returncode": executed.returncode}
                if name.endswith("test_nautilus_pattern_paths.js") and executed.returncode == 0:
                    detail = json.loads(executed.stdout.strip().splitlines()[-1])
                    check.update(check_count=detail["check_count"], controls=detail["controls"])
                    check["passed"] = detail.get("passed") is True
                checks.append(check)
            except Exception as exc:
                checks.append({"path": name, "passed": False, "reason": type(exc).__name__ + ": " + str(exc)})
        js_passed = len(checks) == len(JAVASCRIPT) and all(check["passed"] for check in checks)
        report["javascript"] = {"status": "PASSED" if js_passed else "FAILED", "checks": checks,
                                "pattern_check_count": sum(check.get("check_count", 0) for check in checks)}
        report["javascript_passed"] = js_passed
        report["passed"] = report["passed"] and js_passed
    (args.output / "construct_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("PID10656_LOOKING_GLASS_CONSTRUCT_PASS" if report["passed"] else "PID10656_LOOKING_GLASS_CONSTRUCT_FAIL")
    print(f"Python: {result.testsRun} tests; JavaScript: {report['javascript']['status']}")
    print(args.output / "construct_report.json")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
