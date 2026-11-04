"""Guard the live gauntlet's input/answer separation and paired-case contract."""

import json
from pathlib import Path
import unittest

DRILL_TEST_DEPS = [
    "ventures/armada-battery/interop/tests/edge-fixtures.json",
    "ventures/armada-battery/interop/tests/edge-corpus.script",
]
ROOT = Path(__file__).resolve().parents[1] / "interop" / "tests"
INPUT_KEYS = {"id", "rule", "expected", "acceptance", "observed", "facts"}


class EdgeGauntletTests(unittest.TestCase):
    def setUp(self):
        self.cases = json.loads((ROOT / "edge-fixtures.json").read_text())

    def test_native_inputs_match_fixtures_without_answer_keys(self):
        prefix = 'set request.CaseJSON="'
        inputs = [
            json.loads(line[len(prefix):-1].replace('""', '"'))
            for line in (ROOT / "edge-corpus.script").read_text().splitlines()
            if line.startswith(prefix)
        ]
        self.assertEqual(len(inputs), len(self.cases))
        self.assertEqual(len(inputs), len({row["id"] for row in inputs}))
        for actual, case in zip(inputs, self.cases):
            with self.subTest(case=case["id"]):
                self.assertEqual(set(actual), INPUT_KEYS)
                self.assertEqual(actual, {key: case[key] for key in INPUT_KEYS})

    def test_order_variants_preserve_semantics_and_oracles(self):
        by_id = {case["id"]: case for case in self.cases}
        variants = [case for case in self.cases if "metamorphic_parent" in case]
        self.assertEqual(len(variants), 4)
        for variant in variants:
            parent = by_id[variant["metamorphic_parent"]]
            for field in (INPUT_KEYS - {"id"}) | {"gold", "output_gold", "acceptable_probes"}:
                self.assertEqual(variant[field], parent[field])
            self.assertNotEqual(list(variant["facts"]), list(parent["facts"]))

    def test_missing_observation_is_not_conflated_with_observed_zero(self):
        by_id = {case["id"]: case for case in self.cases}
        for name in ("edge-missing_observation", "edge-unobserved_count", "edge-http202"):
            self.assertEqual((by_id[name]["gold"], by_id[name]["output_gold"]), ("NO", "UNKNOWN"))
        zero = by_id["edge-observed_zero"]
        self.assertEqual((zero["gold"], zero["output_gold"]), ("YES", "PASS"))


if __name__ == "__main__":
    unittest.main()
