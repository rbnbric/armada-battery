from __future__ import annotations

import unittest

from battery.scenarios import run_scenarios


class ScenarioTests(unittest.TestCase):
    def test_all_judging_scenarios(self):
        report = run_scenarios()
        failures = [item for item in report["scenarios"] if not item["passed"]]
        self.assertEqual(failures, [])
        self.assertEqual(report["passed"], report["total"])
        self.assertTrue(
            all(len(item["detail"]) > 30 for item in report["scenarios"]),
            "every passing check should state the property it established",
        )


if __name__ == "__main__":
    unittest.main()
