"""Offline acceptance gate for the standalone Tool Rack PAPER bundle.

This command never starts a feed, reads credentials, or installs dependencies.
The allowlists are also the authoritative package boundary for the builder.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib
import importlib.metadata
import importlib.util
import inspect
import json
from pathlib import Path
import sys
import unittest


MANIFEST_NAME = "TOOL_RACK_PAPER_BUNDLE_MANIFEST.json"
MANIFEST_SCHEMA = "TACHYOS_TOOL_RACK_PAPER_BUNDLE_V1"

CORE_FILES = (
    "strategy_core/__init__.py",
    "strategy_core/types.py",
    "strategy_core/compatibility.py",
    "strategy_core/config_loader.py",
    "strategy_core/lane_resolver.py",
    "strategy_core/router.py",
    "strategy_core/tool_rack.py",
    "strategy_core/commander.py",
    "strategy_core/physical_source.py",
    "strategy_core/paper_feed.py",
    "strategy_core/paper_execution.py",
    "strategy_core/paper_runtime.py",
    "strategy_core/paper_dashboard.py",
    "strategy_core/tools/__init__.py",
    "strategy_core/tools/base.py",
    "strategy_core/tools/management.py",
    "strategy_core/tools/mountain.py",
    "strategy_core/tools/heist.py",
    "strategy_core/tools/rail.py",
    "strategy_core/tools/release.py",
    "strategy_core/detectors/__init__.py",
    "strategy_core/detectors/mountain_geometry.py",
    "strategy_core/detectors/heist_geometry.py",
    "strategy_core/detectors/rail_geometry.py",
    "strategy_core/detectors/release_geometry.py",
    "strategy_core/marketdata/__init__.py",
    "strategy_core/marketdata/common.py",
    "strategy_core/marketdata/btc_observation.py",
    "strategy_core/marketdata/btc_transport.py",
    "strategy_core/marketdata/native_book.py",
    "strategy_core/marketdata/native_receiver.py",
    "strategy_core/marketdata/kalshi_public.py",
)

ASSET_FILES = (
    "strategy_core/config/physical.json",
    "strategy_core/config/mountain.json",
    "strategy_core/config/heist.json",
    "strategy_core/config/rail.json",
    "strategy_core/config/release.json",
    "strategy_core/marketdata/VENDOR_PROVENANCE.json",
    "strategy_core/dashboard/index.html",
    "strategy_core/dashboard/dashboard.css",
    "strategy_core/dashboard/dashboard.js",
)

SUPPORT_FILES = (
    "TOOL_RACK_PAPER.py",
    "TOOL_RACK_EXPORT.py",
    "CHECK_TOOL_RACK_PAPER.py",
    "BUILD_TOOL_RACK_PAPER_BUNDLE.py",
    "01_START_TOOL_RACK_PAPER_90M.cmd",
    "02_CHECK_TOOL_RACK_PAPER.cmd",
    "03_INSTALL_TOOL_RACK_DEPENDENCIES.cmd",
    "04_EXPORT_LAST_TOOL_RACK_RUN.cmd",
    "requirements_tool_rack_paper.txt",
    "README_TOOL_RACK_PAPER.md",
    "docs/TOOL_RACK_PAPER_HANDOFF_2026-10-27.md",
    ".github/workflows/tool-rack-paper.yml",
)

# Deliberately explicit: discovery must not pull migration/shadow tests back in.
TEST_MODULES = (
    "tests.tool_rack.test_commander_end_to_end",
    "tests.tool_rack.test_config_compatibility",
    "tests.tool_rack.test_direct_paper_runtime",
    "tests.tool_rack.test_heist_controller",
    "tests.tool_rack.test_heist_geometry_detector",
    "tests.tool_rack.test_heist_tool",
    "tests.tool_rack.test_mountain_controller",
    "tests.tool_rack.test_mountain_geometry_detector",
    "tests.tool_rack.test_mountain_tool",
    "tests.tool_rack.test_paper_dashboard",
    "tests.tool_rack.test_paper_execution",
    "tests.tool_rack.test_paper_feed",
    "tests.tool_rack.test_paper_launcher_export",
    "tests.tool_rack.test_paper_runtime_accounting",
    "tests.tool_rack.test_pid12156_physical_authority_regressions",
    "tests.tool_rack.test_rail_geometry_detector",
    "tests.tool_rack.test_rail_tool",
    "tests.tool_rack.test_release_geometry_detector",
    "tests.tool_rack.test_release_transition_controller",
    "tests.tool_rack.test_release_watcher",
    "tests.tool_rack.test_router_tool_rack",
    "tests.tool_rack.test_source_gap_reacquisition",
    "tests.tool_rack.test_windows_text_encoding_contract",
)

EXCLUDED_LEGACY_TESTS = (
    "test_event_timeline",
    "test_live_release_transition_integration",
    "test_live_terrain_source_integration",
    "test_nautilus_timeline_patch",
    "test_nautilus_vnext_patch",
    "test_r22_adapter",
    "test_r22_run_source",
    "test_shadow_bundle",
    "test_shadow_compare",
    "test_shadow_engine",
)

TEST_FILES = ("tests/__init__.py", "tests/tool_rack/__init__.py") + tuple(
    module.replace(".", "/") + ".py" for module in TEST_MODULES
)
PACKAGE_FILES = tuple(sorted(CORE_FILES + ASSET_FILES + SUPPORT_FILES + TEST_FILES))
THIRD_PARTY_IMPORTS = frozenset({"websockets", "cryptography"})
INSTALLER_VERSIONS = {"websockets": "16.0", "cryptography": "50.0.2"}

# These tests use the real Commander/executor/journal, not a shadow candidate.
MANDATORY_TEST_METHODS = frozenset({
    "test_sub20_budget_reproduces_138_contracts_and_fee_aware_cash",
    "test_exact_modeled_round_trip_and_committed_net",
    "test_losing_position_can_exit_no_sanctuary",
    "test_armed_floor_cannot_be_lowered_or_waived_and_never_autosells",
    "test_only_official_final_exact_contract_result_settles",
    "test_failed_atomic_commit_never_publishes_uncommitted_position",
    "test_existing_ledger_cannot_be_blindly_restarted",
    "test_raw_causal_down_rail_30c_to_real_committed_paper_fill",
    "test_live_dispatch_rechecks_receive_age_after_measurement_work",
    "test_final_summary_includes_settlement_after_last_decision_snapshot",
    "test_real_rail_floor_exit_then_fresh_value_reentry_uses_single_commander",
})


def module_name(relative: str) -> str:
    name = relative[:-3].replace("/", ".")
    return name[:-9] if name.endswith(".__init__") else name


def audit_package_files(root: Path) -> None:
    """Validate complete files, syntax, UTF-8 I/O and static import closure."""
    selected = set(PACKAGE_FILES)
    if len(selected) != len(PACKAGE_FILES):
        raise ValueError("Duplicate path in PAPER package whitelist")
    missing = [name for name in PACKAGE_FILES if not (root / name).is_file()]
    if missing:
        raise ValueError("Incomplete PAPER package: " + ", ".join(missing))
    modules = {module_name(name) for name in PACKAGE_FILES if name.endswith(".py")}
    local_roots = {name.split(".")[0] for name in modules}
    problems = []
    for relative in PACKAGE_FILES:
        path = root / relative
        if path.resolve() != path.absolute() or path.is_symlink():
            problems.append(relative + ": package sources must be regular, non-symlink files")
        if relative.endswith(".cmd"):
            data = path.read_bytes()
            data.decode("utf-8")
            if data.startswith(b"\xef\xbb\xbf") or b"\n" in data.replace(b"\r\n", b""):
                problems.append(relative + ": launcher requires UTF-8 without BOM and CRLF lines")
            if "INSTALL" not in relative and b"pip install" in data.lower():
                problems.append(relative + ": start/check/export may not install dependencies")
        if not relative.endswith(".py"):
            continue
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=relative)
        compile(tree, relative, "exec")
        current = module_name(relative)
        package = current if relative.endswith("/__init__.py") else current.rpartition(".")[0]
        for node in ast.walk(tree):
            imported = []
            if isinstance(node, ast.Import):
                imported = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    imported = [importlib.util.resolve_name("." * node.level + (node.module or ""), package)]
                elif node.module:
                    imported = [node.module]
            for name in imported:
                top = name.split(".")[0]
                if top in local_roots and name not in modules:
                    problems.append(f"{relative}:{node.lineno}: local import outside whitelist: {name}")
                elif top not in local_roots | THIRD_PARTY_IMPORTS | sys.stdlib_module_names:
                    problems.append(f"{relative}:{node.lineno}: undeclared dependency: {name}")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                attr = node.func.attr
                if attr in ("read_text", "write_text"):
                    explicit = any(key.arg == "encoding" for key in node.keywords)
                    explicit |= len(node.args) >= (1 if attr == "read_text" else 2)
                    if not explicit:
                        problems.append(f"{relative}:{node.lineno}: {attr} requires explicit encoding")
    if problems:
        raise ValueError("PAPER package audit failed:\n" + "\n".join(problems))


def verify_manifest(root: Path, *, required: bool = False) -> bool:
    path = root / MANIFEST_NAME
    if not path.is_file():
        if required:
            raise ValueError("Extracted bundle manifest is missing")
        return False
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise ValueError("Unexpected PAPER bundle manifest schema")
    if manifest.get("mode") != "PAPER" or manifest.get("venue_order_authority") != "NONE":
        raise ValueError("PAPER-only manifest authority mismatch")
    records = manifest.get("files", {})
    if set(records) != set(PACKAGE_FILES):
        raise ValueError("Manifest file set differs from the strict PAPER whitelist")
    for relative, record in records.items():
        data = (root / relative).read_bytes()
        if len(data) != record["size"] or hashlib.sha256(data).hexdigest() != record["sha256"]:
            raise ValueError("Bundle file changed or is incomplete: " + relative)
    for folder in ("strategy_core", "tests"):
        for extra in (root / folder).rglob("*.py"):
            if extra.relative_to(root).as_posix() not in records:
                raise ValueError("Unexpected Python file inside extracted bundle: " + str(extra))
    return True


def check_dependencies() -> dict[str, str]:
    from websockets.sync.client import connect
    import websockets
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

    required = {"additional_headers", "ping_interval", "ping_timeout", "open_timeout", "close_timeout", "max_queue"}
    if not required.issubset(inspect.signature(connect).parameters):
        raise RuntimeError("Existing websockets sync client lacks the required API; run the explicit dependency installer")
    if not callable(websockets.connect) or not callable(serialization.load_pem_private_key):
        raise RuntimeError("Required market-data dependency API is unavailable")
    # Resolve the signing primitives offline without loading any operator key.
    if not all((hashes.SHA256, padding.PSS, padding.MGF1, Ed25519PrivateKey, RSAPrivateKey)):
        raise RuntimeError("Required signing primitives are unavailable")
    return {name: importlib.metadata.version(name) for name in sorted(THIRD_PARTY_IMPORTS)}


def check_loaded_core_modules() -> None:
    allowed = {module_name(name) for name in CORE_FILES}
    forbidden = [name for name in sys.modules if name.startswith("strategy_core.") and name not in allowed]
    if forbidden:
        raise ValueError("Unpackaged or legacy strategy module was imported: " + ", ".join(sorted(forbidden)))


def iter_tests(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from iter_tests(test)
        else:
            yield test


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight-only", action="store_true", help="Validate package, dependencies and imports; do not run tests")
    parser.add_argument("--require-manifest", action="store_true", help="Require and verify an extracted delivery manifest")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parent
    try:
        if sys.version_info < (3, 10):
            raise RuntimeError("Python 3.10 or newer is required; validation targets Python 3.12 and 3.14")
        audit_package_files(root)
        has_manifest = verify_manifest(root, required=args.require_manifest)
        versions = check_dependencies()
        # Imports only: constructors/start functions are not called here.
        for relative in CORE_FILES:
            importlib.import_module(module_name(relative))
        importlib.import_module("TOOL_RACK_PAPER")
        importlib.import_module("TOOL_RACK_EXPORT")
        check_loaded_core_modules()
        print("Tool Rack PAPER | offline package and execution checks", flush=True)
        print(f"Python {sys.version.split()[0]} | " + " | ".join(f"{name} {version}" for name, version in versions.items()), flush=True)
        print(f"Strict whitelist: {len(PACKAGE_FILES)} files; bundle manifest: {'verified' if has_manifest else 'source checkout'}", flush=True)
        different = [name for name, version in versions.items() if version != INSTALLER_VERSIONS[name]]
        if different:
            print("Existing dependency APIs passed; versions differ from installer pins: " + ", ".join(different), flush=True)
        if args.preflight_only:
            print("PREFLIGHT PASSED. No feed, credentials, orders or test run was started.", flush=True)
            return 0
        loader = unittest.TestLoader()
        suite = unittest.TestSuite()
        for module in TEST_MODULES:
            tests = loader.loadTestsFromName(module)
            if tests.countTestCases() == 0:
                raise RuntimeError("Mandatory test module is empty: " + module)
            suite.addTests(tests)
        methods = {test.id().rsplit(".", 1)[-1] for test in iter_tests(suite)}
        missing = MANDATORY_TEST_METHODS - methods
        if missing:
            raise RuntimeError("Real PAPER execution tests are missing: " + ", ".join(sorted(missing)))
        print(f"Running {suite.countTestCases()} tests in {len(TEST_MODULES)} explicitly selected modules.", flush=True)
        result = unittest.TextTestRunner(verbosity=2 if args.verbose else 1, buffer=True).run(suite)
        check_loaded_core_modules()
        if not result.wasSuccessful() or result.skipped:
            print("CHECK FAILED. All selected PAPER tests must run and pass without skips.", flush=True)
            return 1
        print(f"CHECK PASSED: {result.testsRun} tests. No live market session or venue order was started.", flush=True)
        return 0
    except Exception as exc:
        print(f"CHECK FAILED: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        print("Extract the whole PAPER bundle. For missing/incompatible packages, run 03_INSTALL_TOOL_RACK_DEPENDENCIES.cmd explicitly.", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
