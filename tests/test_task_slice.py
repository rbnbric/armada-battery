from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from battery.ledger import Ledger
from battery.models import RuleValidation
from battery.task_slice import BatteryEngine, SyntheticTaskAdapter


class Clock:
    def __init__(self) -> None:
        self.value = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.value

    def advance(self, seconds: int) -> None:
        self.value += timedelta(seconds=seconds)


class TaskSliceTests(unittest.TestCase):
    def engine(self, adapter=None, **kwargs):
        return BatteryEngine(
            adapter or SyntheticTaskAdapter(),
            ledger=Ledger(),
            **kwargs,
        )

    def prepare(self, engine):
        return engine.prepare_task_run(
            17,
            requested_by="test-operator",
            task_definition_reviewed=True,
        )

    def test_intent_without_incident_prepares_action(self):
        engine = self.engine()
        result = self.prepare(engine)

        self.assertEqual(result["intent"]["kind"], "RUN")
        self.assertEqual(result["finding"]["state"], "SAFE")
        self.assertIsNotNone(result["certificate"])
        self.assertIn("counterexamples", result["rule"])
        self.assertTrue(engine.ledger.verify())

    def test_prior_failure_does_not_imply_retry(self):
        engine = self.engine(SyntheticTaskAdapter(prior_failure=True))
        result = self.prepare(engine)

        self.assertEqual(result["finding"]["state"], "BLOCKED")
        self.assertIsNone(result["certificate"])
        combined = " ".join(result["finding"]["missing_evidence"])
        self.assertIn("failure alone does not prove", combined)
        self.assertIn("cause-specific remedy", result["finding"]["recommended_actions"][0])

    def test_latest_history_is_selected_by_time_not_response_order(self):
        adapter = SyntheticTaskAdapter(prior_failure=True)
        adapter.history[17].insert(0, {
            "TaskId": 17,
            "LastStart": "2026-09-23T11:00:00+00:00",
            "Completed": "2026-09-23T11:00:02+00:00",
            "LogDatetime": "2026-09-23T11:00:02+00:00",
            "Status": "Success",
            "Result": "Success",
        })
        engine = self.engine(adapter)

        result = self.prepare(engine)

        self.assertEqual(result["finding"]["state"], "SAFE")
        self.assertIsNotNone(result["certificate"])

    def test_unvalidated_rule_can_explain_but_not_unlock_change(self):
        engine = self.engine(rule_validation=RuleValidation.DRAFT)
        result = self.prepare(engine)

        self.assertEqual(result["finding"]["state"], "BLOCKED")
        self.assertIsNone(result["certificate"])
        self.assertIn("execution requires SIMULATED", " ".join(result["finding"]["missing_evidence"]))

    def test_missing_history_privilege_blocks_verification_and_execution(self):
        engine = self.engine(SyntheticTaskAdapter(operate_privilege=False))
        result = self.prepare(engine)

        self.assertEqual(result["finding"]["state"], "BLOCKED")
        self.assertIn("%Admin_Operate:U", " ".join(result["finding"]["missing_evidence"]))

    def test_success_requires_new_history_observation(self):
        engine = self.engine()
        prepared = self.prepare(engine)
        receipt = engine.execute_task_run(prepared["certificate"]["token"], "run-1")

        self.assertEqual(receipt["status"], "VERIFIED_SUCCESS")
        self.assertEqual(len(receipt["after_evidence"]), 1)

    def test_idempotency_does_not_repeat_run(self):
        adapter = SyntheticTaskAdapter()
        engine = self.engine(adapter)
        prepared = self.prepare(engine)
        token = prepared["certificate"]["token"]

        first = engine.execute_task_run(token, "same-key")
        second = engine.execute_task_run(token, "same-key")

        self.assertEqual(first["id"], second["id"])
        self.assertEqual(adapter.run_calls, 1)

    def test_ambiguous_transport_never_retries_and_can_reconcile(self):
        adapter = SyntheticTaskAdapter(ambiguous=True)
        engine = self.engine(adapter)
        prepared = self.prepare(engine)

        receipt = engine.execute_task_run(prepared["certificate"]["token"], "ambiguous-1")
        self.assertEqual(receipt["status"], "OUTCOME_UNKNOWN")
        repeated = engine.execute_task_run(prepared["certificate"]["token"], "ambiguous-1")
        self.assertEqual(repeated["id"], receipt["id"])
        self.assertEqual(adapter.run_calls, 1)

        adapter.reveal_pending()
        reconciled = engine.reconcile(receipt["id"])
        self.assertEqual(reconciled["status"], "VERIFIED_SUCCESS")
        self.assertEqual(adapter.run_calls, 1)

    def test_expired_preflight_requires_preparation_again(self):
        clock = Clock()
        engine = self.engine(now=clock)
        prepared = self.prepare(engine)
        clock.advance(61)

        with self.assertRaisesRegex(ValueError, "expired"):
            engine.execute_task_run(prepared["certificate"]["token"], "late-run")

    def test_task_change_after_preflight_invalidates_certificate(self):
        adapter = SyntheticTaskAdapter()
        engine = self.engine(adapter)
        prepared = self.prepare(engine)
        adapter.tasks[17]["Description"] = "Changed after preparation"

        with self.assertRaisesRegex(ValueError, "changed after preflight"):
            engine.execute_task_run(prepared["certificate"]["token"], "changed-run")


if __name__ == "__main__":
    unittest.main()
