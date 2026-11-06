"""Offline two-lane Construct: positive advisers, first-fade calibration and safe custody.

No feeds, credentials, exchange orders, or PAPER sessions are started.
All controls are deterministic and based on the current approved source APIs.
"""
from __future__ import annotations

import unittest
from tests.tool_rack.test_dual_lane_main_tactical import DualLaneTests


def main() -> int:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(DualLaneTests)
    total = suite.countTestCases()
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful() or result.testsRun != total:
        print(f"DUAL LANE CONSTRUCT FAILED: {result.testsRun} / {total}")
        return 1
    print(f"DUAL LANE CONSTRUCT PASS: {result.testsRun}/{total} controls passed")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
