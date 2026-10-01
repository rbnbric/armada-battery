from __future__ import annotations

import unittest

from scripts.verify_sandbox import CORE_TEST_FILES, build_report


class SandboxVerifierTests(unittest.TestCase):
    def test_covers_the_dependency_free_engine_suite(self):
        self.assertEqual(
            CORE_TEST_FILES,
            (
                "test_task_slice.py",
                "test_admin_slice.py",
                "test_inventory.py",
                "test_scenarios.py",
                "test_runtime_safety.py",
            ),
        )
        report = build_report()
        self.assertTrue(report["passed"])
        self.assertEqual(report["core"]["tests_run"], 39)
        self.assertEqual(report["scenarios"]["passed"], 8)
        self.assertEqual(report["scenarios"]["total"], 8)
        self.assertEqual(set(report["excluded"]), {"tests/test_api.py"})


if __name__ == "__main__":
    unittest.main()
