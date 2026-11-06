"""Exact PID15740 counterwind and inherited-opening source-path controls."""
from __future__ import annotations
import unittest
from tests.tool_rack.test_pid15740_inherited_up_rail import PID15740InheritedUpRailTests

def main():
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(PID15740InheritedUpRailTests)
    total=suite.countTestCases(); res=unittest.TextTestRunner(verbosity=1).run(suite)
    if not res.wasSuccessful() or res.testsRun != total:
        print(f'PID15740 CONSTRUCT FAILED: {res.testsRun}/{total}');return 1
    print(f'PID15740 CONSTRUCT PASS: {res.testsRun}/{total} recorded/mirrored controls passed')
    return 0
if __name__=='__main__':raise SystemExit(main())
