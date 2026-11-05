"""Scorer integrity tests. Mock proof output tests parsing, never native qualification."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DRILL_TEST_DEPS = ["ventures/armada-battery/scripts/ship_compare_layers.py", "ventures/armada-battery/interop/results/implementation-109.json"]
spec = importlib.util.spec_from_file_location("comparison", ROOT / "scripts/ship_compare_layers.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
SOURCE = ROOT / "interop/results/implementation-109.json"

class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / "source.json"
        data = json.loads(SOURCE.read_text())
        # Small retained subset; the scorer may not quietly discard bad records.
        data["native_rows"] = [r for r in data["native_rows"] if r["live"] == 1][:3]
        self.source.write_text(json.dumps(data)); self.data = data
        self.rows = m.load_cases(self.source); self.items = m.snapshots(self.rows)
        self.proof = {"verdict": "NO", "output": "UNKNOWN", "usable": False}
        self.lines = ["COMPARISON_BEGIN=unit-test-fake"] + [
            "COMPARISON_ROW=" + i["key"] + "|" + json.dumps(self.proof) for i in self.items] + ["COMPARISON_END"]
        self.log = Path(self.temp.name) / "native.log"
    def save_source(self):
        self.source.write_text(json.dumps(self.data))
    def test_preparation_never_transmits_expected_labels_or_invokes_agents(self):
        script = m.prepare(self.source)
        self.assertEqual(script.count(".Assess("), 6)
        for forbidden in ["expected_state", "AgentOperation", "StartProduction", "%Save", "SendRequest"]:
            self.assertNotIn(forbidden, script)
    def test_fixed_corpus_keeps_all_24_real_model_cases(self):
        rows = m.load_cases(SOURCE)
        self.assertEqual(len(rows), 24)
        self.assertEqual(len({r["mode"] for r in rows}), 8)
    def test_duplicate_source_cases_refused(self):
        self.data["native_rows"].append(self.data["native_rows"][0]); self.save_source()
        with self.assertRaises(ValueError): m.load_cases(self.source)
    def test_missing_final_read_refused(self):
        self.data["native_rows"][0]["reads"].pop(); self.save_source()
        with self.assertRaises(ValueError): m.load_cases(self.source)
    def test_changed_contract_refused(self):
        self.data["native_rows"][0]["reads"][-1]["contract"] = "{}"; self.save_source()
        with self.assertRaises(ValueError): m.load_cases(self.source)
    def test_native_record_omission_refused(self):
        with self.assertRaises(ValueError): m.parse_native("\n".join(self.lines[:2] + self.lines[3:]), self.items)
    def test_duplicate_native_record_refused(self):
        with self.assertRaises(ValueError): m.parse_native("\n".join(self.lines + [self.lines[1]]), self.items)
    def test_wrong_snapshot_binding_refused(self):
        self.lines[1] = self.lines[1].replace(self.items[0]["key"], "f"*64)
        with self.assertRaises(ValueError): m.parse_native("\n".join(self.lines), self.items)
    def test_missing_end_marker_refused(self):
        with self.assertRaises(ValueError): m.parse_native("\n".join(self.lines[:-1]), self.items)
    def test_native_errors_refused_even_with_end_marker(self):
        with self.assertRaises(ValueError): m.parse_native("\n".join(self.lines + ["<UNDEFINED>zAssess+2"]), self.items)
    def test_unknown_cannot_be_promoted_to_pass(self):
        self.lines[1] = self.lines[1].replace('"UNKNOWN"', '"PASS"')
        with self.assertRaises(ValueError): m.parse_native("\n".join(self.lines), self.items)
    def test_failed_comparison_is_counted_not_filtered(self):
        self.log.write_text("\n".join(self.lines))
        result = m.score(self.source, self.log)
        self.assertEqual(result["summary"]["cases"], 3)
        self.assertEqual(result["summary"]["rules_final_evidence"], 1)
        self.assertEqual(len(result["rows"]), 3)
        self.assertEqual(result["new_model_calls"], 0)
        self.assertGreater(result["historical_model_usage"]["calls"], 0)
    def test_usage_absence_is_not_reported_as_zero(self):
        calls = json.loads(self.data["native_rows"][0]["reviews"][0]["agent_calls"])
        calls[0]["usage"] = "{}"
        self.data["native_rows"][0]["reviews"][0]["agent_calls"] = json.dumps(calls); self.save_source()
        self.log.write_text("\n".join(self.lines))
        with self.assertRaises(ValueError): m.score(self.source, self.log)
    def test_objectscript_literal_escapes_quotes_and_rejects_newlines(self):
        self.assertEqual(m.os_string('a"b'), '\"a\"\"b\"')
        with self.assertRaises(ValueError): m.os_string("a\nb")

if __name__ == "__main__": unittest.main()
