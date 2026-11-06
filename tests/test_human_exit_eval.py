"""The blind comparison uses identical case facts and a reproducible sample."""
import json
import tempfile
import unittest
from pathlib import Path

from interop.tests.human_exit_eval import prepare
from interop.tests.claim_review_eval import prepare as prepare_claim_review


class HumanExitTrialTests(unittest.TestCase):
    def test_claim_review_trial_blinds_arms_and_preserves_facts(self):
        for holdout in (False, True):
            with tempfile.TemporaryDirectory() as directory:
                prepare_claim_review(Path(directory), holdout=holdout)
                rows=json.loads((Path(directory)/'packets.json').read_text())['rows']
                self.assertEqual(len(rows),12)
                for index in range(0,len(rows),3):
                    trio=rows[index:index+3]
                    self.assertEqual([r['arm'] for r in trio],['worst_case','perfect','random_incompetence'])
                    self.assertEqual(len({json.dumps(r['packet']['facts'],sort_keys=True) for r in trio}),1)
                    for row in trio:
                        self.assertNotIn(row['arm'],json.dumps(row['packet']))
                        self.assertLessEqual(len(json.dumps(row['packet'],sort_keys=True,separators=(',',':')).encode()),6144)
    def test_three_arms_change_only_the_human_response(self):
        with tempfile.TemporaryDirectory() as directory:
            prepare(Path(directory))
            result=json.loads((Path(directory)/'packets.json').read_text())
            rows=result['rows']
            self.assertEqual(len(rows),9)
            self.assertEqual({row['arm'] for row in rows},{'worst_case','perfect','random_incompetence'})
            for index in range(0,len(rows),3):
                trio=rows[index:index+3]
                self.assertEqual([row['arm'] for row in trio],['worst_case','perfect','random_incompetence'])
                self.assertEqual(len({row['scenario'] for row in trio}),1)
                self.assertEqual(len({json.dumps(row['packet']['sources'][:4],sort_keys=True) for row in trio}),1)
                self.assertEqual(len({json.dumps(row['packet']['sources'][4],sort_keys=True) for row in trio}),3)
                for row in trio:
                    self.assertNotIn(row['arm'],json.dumps(row['packet']))
                    self.assertLessEqual(len(json.dumps(row['packet'],sort_keys=True,separators=(',',':')).encode()),6144)

    def test_accountability_excuses_keep_machine_evidence_fixed(self):
        with tempfile.TemporaryDirectory() as directory:
            prepare(Path(directory), accountability=True)
            result=json.loads((Path(directory)/'packets.json').read_text())
            rows=result['rows']
            self.assertEqual(len(rows),12)
            self.assertEqual(len({row['scenario'] for row in rows}),4)
            for index in range(0,len(rows),3):
                trio=rows[index:index+3]
                self.assertEqual([row['arm'] for row in trio],['worst_case','perfect','random_incompetence'])
                self.assertEqual(len({json.dumps(row['packet']['sources'][:4],sort_keys=True) for row in trio}),1)
                for row in trio:
                    self.assertNotIn(row['arm'],json.dumps(row['packet']))
                    self.assertLessEqual(len(json.dumps(row['packet'],sort_keys=True,separators=(',',':')).encode()),6144)


if __name__=='__main__': unittest.main()
