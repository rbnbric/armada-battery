"""Run Battery's dependency-free verification suite in the venture sandbox.

The sandbox image deliberately carries only Python's standard library. The
FastAPI surface is exercised by the normal venture test suite and application
image; this runner proves the decision engine and judging scenarios without
network access, credentials, or dependency installation.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from battery.scenarios import run_scenarios  # noqa: E402


CORE_TEST_FILES = (
    "test_task_slice.py",
    "test_admin_slice.py",
    "test_inventory.py",
    "test_scenarios.py",
    "test_runtime_safety.py",
)


def run_core_tests() -> dict[str, object]:
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for filename in CORE_TEST_FILES:
        suite.addTests(loader.discover(str(ROOT / "tests"), pattern=filename))
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=1).run(suite)
    return {
        "passed": result.wasSuccessful(),
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "detail": stream.getvalue()[-4000:],
    }


def build_report() -> dict[str, object]:
    core = run_core_tests()
    scenarios = run_scenarios()
    passed = bool(core["passed"] and scenarios["passed"] == scenarios["total"])
    return {
        "passed": passed,
        "profile": "full",
        "core": core,
        "scenarios": scenarios,
        "excluded": {
            "tests/test_api.py": (
                "FastAPI dependency belongs to the application image; normal venture tests cover it."
            )
        },
    }


if __name__ == "__main__":
    report = build_report()
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["passed"] else 1)
