"""Contract checks for the direct-model benchmark; no provider call."""

from __future__ import annotations

import unittest

from scripts.eval_interop_agents import CASES, validate_investigation, validate_review


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

    def test_investigator_cannot_invent_a_probe(self):
        case = CASES[1]
        with self.assertRaisesRegex(ValueError, "invalid investigation probe"):
            validate_investigation({"next_probe": "SEND_AGAIN", "evidence_ids": ["B1"], "hypothesis": "Try it", "uncertainty": "Unknown"}, case)

    def test_investigator_cannot_cite_fabricated_evidence(self):
        case = CASES[1]
        with self.assertRaisesRegex(ValueError, "absent evidence"):
            validate_investigation({"next_probe": "CHECK_TARGET_VERSION", "evidence_ids": ["fake"], "hypothesis": "Version drift", "uncertainty": "Unconfirmed"}, case)


if __name__ == "__main__":
    unittest.main()
