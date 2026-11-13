"""Exercise the result verifier against retained native output and damaged copies."""
import importlib.util
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
DRILL_TEST_DEPS = ["ventures/armada-battery/interop/tests/verify_bonus_results.py"]
SPEC = importlib.util.spec_from_file_location("bonus_results", ROOT / "interop/tests/verify_bonus_results.py")
VERIFIER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFIER)


class BonusResultTests(unittest.TestCase):
    def setUp(self):
        self.logs = [(ROOT / f"interop/results/bonus-{name}-109.log").read_text()
                     for name in ("qualification", "regression", "proof")]

    def test_retained_native_run(self):
        result = VERIFIER.verify(*self.logs)
        self.assertEqual(result["passed"], 247)
        self.assertEqual(result["failed"], 0)

    def test_missing_completion(self):
        self.logs[0] = self.logs[0].replace("BONUS_QUALIFICATION_OK", "")
        with self.assertRaisesRegex(ValueError, "Missing completion"):
            VERIFIER.verify(*self.logs)

    def test_missing_check(self):
        self.logs[2] = re.sub(r"PROOF_CHECK=\{[^\n]*\}", "", self.logs[2], count=1)
        with self.assertRaisesRegex(ValueError, "proof: expected"):
            VERIFIER.verify(*self.logs)

    def test_failed_check(self):
        self.logs[0] = self.logs[0].replace('"name":"real_http_read","passed":1',
                                            '"name":"real_http_read","passed":0')
        with self.assertRaisesRegex(ValueError, "failed check real_http_read"):
            VERIFIER.verify(*self.logs)

    def test_duplicate_replaces_missing_proof(self):
        rows = list(re.finditer(r"PROOF_CHECK=\{[^\n]*\}", self.logs[2]))
        self.logs[2] = self.logs[2][:rows[1].start()] + rows[0].group() + self.logs[2][rows[1].end():]
        with self.assertRaisesRegex(ValueError, "proof: duplicate"):
            VERIFIER.verify(*self.logs)

    def test_native_failure_after_success(self):
        self.logs[1] += "\nFAULT_SUITE_ERROR=failed after earlier cases\n"
        with self.assertRaisesRegex(ValueError, "Native error"):
            VERIFIER.verify(*self.logs)

    def test_missing_restart_check_replaced_with_another_fault(self):
        self.logs[1] = self.logs[1].replace('"mode":"agree"', '"mode":"yes_fail"', 1)
        with self.assertRaisesRegex(ValueError, "fault sequence"):
            VERIFIER.verify(*self.logs)


if __name__ == "__main__":
    unittest.main()
