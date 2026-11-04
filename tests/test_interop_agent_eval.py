"""Contract checks for the direct-model benchmark; no provider call."""

from __future__ import annotations

import unittest

import runpy
from pathlib import Path

DRILL_TEST_DEPS = ["ventures/armada-battery/scripts/eval_interop_agents.py"]

# Load the real adjacent script without claiming the fleet-wide scripts namespace.
_evaluator = runpy.run_path(str(Path(__file__).resolve().parents[1] / "scripts/eval_interop_agents.py"))
CASES = _evaluator["CASES"]
validate_investigation = _evaluator["validate_investigation"]
validate_review = _evaluator["validate_review"]


class InteropAgentContractTests(unittest.TestCase):
    def test_every_case_has_distinct_ground_truth_and_cited_facts(self):
        self.assertEqual(len(CASES), len({case["id"] for case in CASES}))
        self.assertEqual({case["gold"] for case in CASES}, {"YES", "NO"})
        self.assertTrue(all(case["facts"] and case["expected"] and case["acceptance"] and case["observed"] and case["output_gold"] for case in CASES))

    def test_yes_requires_an_applicable_rule(self):
        case = CASES[0]
        with self.assertRaisesRegex(ValueError, "disagree"):
            validate_review({"verdict": "YES", "applicability": "INAPPLICABLE", "output_result": "PASS", "evidence_ids": ["A1"], "summary": "No"}, case)

    def test_review_cannot_cite_fabricated_evidence(self):
        case = CASES[0]
        with self.assertRaisesRegex(ValueError, "absent evidence"):
            validate_review({"verdict": "YES", "applicability": "APPLICABLE", "output_result": "PASS", "evidence_ids": ["fake"], "summary": "Yes"}, case)

    def test_inapplicable_assertion_can_coexist_with_passing_output(self):
        case = next(case for case in CASES if case["id"] == "required_field_false_positive")
        review = validate_review({"verdict": "NO", "applicability": "INAPPLICABLE", "output_result": "PASS", "evidence_ids": ["D1", "D2"], "summary": "The rule is out of context; accepting this valid input passes."}, case)
        self.assertEqual((review["verdict"], review["output_result"]), ("NO", "PASS"))

    def test_accurate_assertion_can_coexist_with_failing_output(self):
        case = next(case for case in CASES if case["id"] == "accurate_rule_bad_output")
        review = validate_review({"verdict": "YES", "applicability": "APPLICABLE", "output_result": "FAIL", "evidence_ids": ["A3", "A4"], "summary": "Validation passed, but the duplicate effect fails acceptance."}, case)
        self.assertEqual((review["verdict"], review["output_result"]), ("YES", "FAIL"))

    def test_investigator_cannot_invent_a_probe(self):
        case = CASES[1]
        with self.assertRaisesRegex(ValueError, "invalid investigation probe"):
            validate_investigation({"next_probe": "SEND_AGAIN", "evidence_ids": ["B1"], "hypothesis": "Try it", "uncertainty": "Unknown"}, case)

    def test_investigator_cannot_cite_fabricated_evidence(self):
        case = CASES[1]
        with self.assertRaisesRegex(ValueError, "absent evidence"):
            validate_investigation({"next_probe": "CHECK_TARGET_VERSION", "evidence_ids": ["fake"], "hypothesis": "Version drift", "uncertainty": "Unconfirmed"}, case)

    def test_unobserved_application_state_is_not_a_successful_hold(self):
        case = next(case for case in CASES if case["id"] == "missing_observation")
        self.assertEqual((case["gold"], case["output_gold"]), ("NO", "UNKNOWN"))
        review = validate_review({"verdict": "NO", "applicability": "UNKNOWN", "output_result": "UNKNOWN", "evidence_ids": ["K1", "K2"], "summary": "Application state has not been observed."}, case)
        self.assertEqual(review["output_result"], "UNKNOWN")

    def test_reassessment_contract_regressions(self):
        valid = {"verdict": "YES", "applicability": "APPLICABLE", "output_result": "PASS", "evidence_ids": ["A1"], "summary": "Observed"}
        for field, value in [("summary", 17), ("summary", {}), ("summary", "   "), ("evidence_ids", ["A1", "A1"]), ("execute", "SEND_NOW")]:
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                validate_review({**valid, field: value}, CASES[0])
        with self.assertRaises(ValueError):
            validate_review(valid, {**CASES[0], "facts": {"A1": {}}})


if __name__ == "__main__":
    unittest.main()
