"""Adversarial execution invariants, using disposable state and no live IRIS."""

import json
import multiprocessing
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from battery.task_slice import BatteryEngine, SyntheticTaskAdapter
from battery.ledger import Ledger
from battery.errors import AdapterError


def plan(engine):
    return engine.prepare_task_run(
        17, requested_by="operator", task_definition_reviewed=True
    )["certificate"]["token"]


def create_plan(engine):
    return engine.prepare_create_web_app(
        name="/api/probe",
        namespace="USER",
        dispatch_class="Demo.Probe",
        resource="App.Reader",
        requested_by="operator",
    )["certificate"]["token"]


class SlowAdapter(SyntheticTaskAdapter):
    def get_task(self, task_id):
        time.sleep(0.02)
        return super().get_task(task_id)


class ReadbackFails(SyntheticTaskAdapter):
    def get_web_app(self, name):
        if name in self.web_apps and name == "/api/probe":
            raise AdapterError("HTTP 503")
        return super().get_web_app(name)


class RuntimeSafetyTests(unittest.TestCase):
    def test_simultaneous_same_key_one_dispatch_across_engines(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.jsonl"
            adapter = SlowAdapter()
            first = BatteryEngine(adapter, ledger=Ledger(path))
            token = plan(first)
            second = BatteryEngine(adapter, ledger=Ledger(path))
            gate = threading.Barrier(2)

            def run(engine):
                gate.wait()
                return engine.execute_task_run(token, "shared", operator="operator")

            with ThreadPoolExecutor(2) as pool:
                results = list(pool.map(run, [first, second]))
            self.assertEqual(adapter.run_calls, 1)
            self.assertEqual(results[0]["id"], results[1]["id"])
            self.assertTrue(first.ledger.verify())

    def test_separate_processes_share_one_durable_dispatch_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.jsonl"
            initial = BatteryEngine(SyntheticTaskAdapter(), ledger=Ledger(path))
            token = plan(initial)
            context = multiprocessing.get_context("fork")
            calls = context.Value("i", 0)
            gate = context.Event()
            results = context.Queue()

            def worker():
                class CountAdapter(SyntheticTaskAdapter):
                    def run_task(self, task_id):
                        with calls.get_lock():
                            calls.value += 1
                        return super().run_task(task_id)

                engine = BatteryEngine(CountAdapter(), ledger=Ledger(path))
                gate.wait(5)
                results.put(engine.execute_task_run(token, "process-key")["id"])

            workers = [context.Process(target=worker) for _ in range(2)]
            for child in workers:
                child.start()
            gate.set()
            ids = [results.get(timeout=5) for _ in workers]
            for child in workers:
                child.join(5)
                self.assertEqual(child.exitcode, 0)
            self.assertEqual(calls.value, 1)
            self.assertEqual(len(set(ids)), 1)

    def test_restart_recovers_unknown_attempt_without_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.jsonl"
            adapter = SyntheticTaskAdapter(ambiguous=True)
            first = BatteryEngine(adapter, ledger=Ledger(path))
            token = plan(first)
            receipt = first.execute_task_run(token, "lost")
            second = BatteryEngine(adapter, ledger=Ledger(path))
            adapter.reveal_pending()
            self.assertEqual(
                second.reconcile(receipt["id"])["status"], "VERIFIED_SUCCESS"
            )
            self.assertEqual(
                second.execute_task_run(token, "lost")["id"], receipt["id"]
            )
            self.assertEqual(adapter.run_calls, 1)

    def test_restart_recovers_administrative_payload_and_evidence(self):
        class LostReply(SyntheticTaskAdapter):
            def put_web_app(self, name, payload):
                super().put_web_app(name, payload)
                raise KeyboardInterrupt("process died after dispatch")

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.jsonl"
            adapter = LostReply()
            first = BatteryEngine(adapter, ledger=Ledger(path))
            token = create_plan(first)
            with self.assertRaises(KeyboardInterrupt):
                first.execute_admin(token, "crash")
            second = BatteryEngine(adapter, ledger=Ledger(path))
            receipt = second.list_receipts()[0]
            self.assertEqual(receipt["status"], "OUTCOME_UNKNOWN")
            result = second.reconcile(receipt["id"])
            self.assertEqual(result["status"], "VERIFIED_SUCCESS")
            self.assertTrue(result["before_evidence"])
            self.assertTrue(result["after_evidence"])

    def test_readback_failure_is_not_mutation_failure(self):
        adapter = ReadbackFails()
        engine = BatteryEngine(adapter, ledger=Ledger())
        receipt = engine.execute_admin(create_plan(engine), "readback")
        self.assertEqual(receipt["status"], "OUTCOME_UNKNOWN")
        self.assertIn("/api/probe", adapter.web_apps)

    def test_old_or_unattributable_history_cannot_prove_success(self):
        adapter = SyntheticTaskAdapter(ambiguous=True)
        engine = BatteryEngine(adapter, ledger=Ledger())
        token = plan(engine)
        adapter.history[17].append(
            {
                "TaskId": 17,
                "LastStart": "2000-01-01T00:00:00+00:00",
                "Status": "Success",
            }
        )
        receipt = engine.execute_task_run(token, "old")
        self.assertNotEqual(
            engine.reconcile(receipt["id"])["status"], "VERIFIED_SUCCESS"
        )
        adapter.synthetic = False
        adapter.reveal_pending()
        self.assertNotEqual(
            engine.reconcile(receipt["id"])["status"], "VERIFIED_SUCCESS"
        )

    def test_exact_status_classification(self):
        for value in [
            "Unsuccessful",
            "Incomplete",
            "Not completed",
            "Success; no errors",
        ]:
            self.assertNotEqual(
                BatteryEngine._history_outcome({"Status": value}), "success"
            )

    def test_write_failure_prevents_dispatch(self):
        adapter = SyntheticTaskAdapter()
        engine = BatteryEngine(adapter, ledger=Ledger())
        token = plan(engine)
        with patch.object(
            engine.ledger, "append", side_effect=OSError("disk unavailable")
        ):
            with self.assertRaises(OSError):
                engine.execute_task_run(token, "disk")
        self.assertEqual(adapter.run_calls, 0)

    def test_operator_and_conflicting_key_are_rejected(self):
        adapter = SyntheticTaskAdapter()
        engine = BatteryEngine(adapter, ledger=Ledger())
        token = plan(engine)
        with self.assertRaises(ValueError):
            engine.execute_task_run(token, "actor", operator="other")
        engine.execute_task_run(token, "same", operator="operator")
        another = plan(engine)
        with self.assertRaises(ValueError):
            engine.execute_task_run(another, "same", operator="operator")
        self.assertEqual(adapter.run_calls, 1)

    def test_secret_canary_and_raw_certificate_are_not_persisted(self):
        adapter = SyntheticTaskAdapter()
        adapter.tasks[17]["Settings"] = {"Password": "CANARY_NON_SECRET"}
        engine = BatteryEngine(adapter, ledger=Ledger())
        token = plan(engine)
        text = json.dumps(engine.ledger.records)
        self.assertNotIn("CANARY_NON_SECRET", text)
        self.assertNotIn(token, text)
        self.assertIn("[REDACTED]", text)

    def test_partial_privilege_keeps_tasks_available(self):
        class TaskOnly(SyntheticTaskAdapter):
            def list_users(self):
                raise AdapterError("HTTP 403")

        engine = BatteryEngine(TaskOnly(), ledger=Ledger())
        catalog = engine.admin_catalog()
        self.assertEqual(catalog["quality"]["users"]["quality"], "FORBIDDEN")
        self.assertEqual(len(catalog["tasks"]), 1)

    def test_empty_ledger_has_no_head(self):
        result = BatteryEngine(SyntheticTaskAdapter(), ledger=Ledger()).audit_trail()
        self.assertEqual(result["count"], 0)
        self.assertIsNone(result["head"])
