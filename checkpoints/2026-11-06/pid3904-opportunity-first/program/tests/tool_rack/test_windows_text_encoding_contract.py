import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

SCAN_DIRS = (
    ROOT / "strategy_core",
    ROOT / "tests" / "tool_rack",
    ROOT / "nautilus_vnext",
)

SCAN_ROOT_FILES = (
    ROOT / "CHECK_TOOL_RACK_V1.py",
    ROOT / "BUILD_TOOL_RACK_SHADOW_BUNDLE.py",
    ROOT / "TOOL_RACK_ATTACH_R22_SHADOW.py",
    ROOT / "TOOL_RACK_SHADOW_REPLAY.py",
    ROOT / "TOOL_RACK_COMPARE_SHADOW_TO_PAPER.py",
)


def python_files():
    for directory in SCAN_DIRS:
        if directory.is_dir():
            yield from directory.rglob("*.py")
    for path in SCAN_ROOT_FILES:
        if path.is_file():
            yield path


class WindowsTextEncodingContractTests(unittest.TestCase):
    def test_pathlib_text_io_is_explicit_utf8(self):
        violations = []
        for path in sorted(set(python_files())):
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                if not isinstance(node.func, ast.Attribute):
                    continue
                attr = node.func.attr
                if attr not in ("read_text", "write_text"):
                    continue

                explicit_keyword = any(
                    keyword.arg == "encoding"
                    for keyword in node.keywords
                )
                if attr == "read_text":
                    explicit_positional = len(node.args) >= 1
                else:
                    # Path.write_text(data, encoding=...) — the first
                    # positional argument is data, the second is encoding.
                    explicit_positional = len(node.args) >= 2

                if not explicit_keyword and not explicit_positional:
                    violations.append(
                        f"{path.relative_to(ROOT)}:{node.lineno} "
                        f"{attr}() missing explicit encoding"
                    )

        self.assertEqual(
            violations,
            [],
            "Windows can default Path.read_text/write_text to cp1252. "
            "Every Tool Rack text I/O call must declare UTF-8 explicitly.\n"
            + "\n".join(violations),
        )


if __name__ == "__main__":
    unittest.main()
