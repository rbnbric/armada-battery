from __future__ import annotations

import unittest
from unittest.mock import patch
import os

from fastapi.testclient import TestClient

import importlib.util
import sys
from pathlib import Path

from battery.ledger import Ledger
from battery.task_slice import BatteryEngine, SyntheticTaskAdapter

DRILL_TEST_DEPS = ["ventures/armada-battery/app.py"]

_spec = importlib.util.spec_from_file_location(
    "armada_battery_app", Path(__file__).resolve().parents[1] / "app.py"
)
web = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = web
with patch(
    "battery.task_slice.engine_from_environment",
    return_value=BatteryEngine(SyntheticTaskAdapter(), ledger=Ledger()),
):
    _spec.loader.exec_module(web)


class ApiTests(unittest.TestCase):
    def setUp(self):
        web.engine = BatteryEngine(SyntheticTaskAdapter(), ledger=Ledger())
        self.client = TestClient(web.app)

    def test_catalog_and_security_headers(self):
        response = self.client.get("/api/catalog")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["namespaces"], ["USER"])
        self.assertIn(
            "frame-ancestors 'none'", response.headers["content-security-policy"]
        )

        observations = self.client.get("/api/observations").json()["areas"]
        self.assertEqual(len(observations), 8)
        self.assertTrue(
            all(item["quality"] == "VALID" for item in observations.values())
        )
        self.assertNotIn("secret value", str(observations).lower())

        assurance = self.client.get("/api/assurance").json()
        self.assertEqual((assurance["passed"], assurance["total"]), (8, 8))
        evidence = self.client.get("/api/evidence").json()
        self.assertTrue(evidence["valid"])

    def test_web_app_prepare_execute_and_readback(self):
        prepared = self.client.post(
            "/api/intents/web-app/create",
            json={
                "name": "/api/orders",
                "namespace": "USER",
                "dispatch_class": "Demo.Orders",
                "resource": "App.Reader",
            },
        )
        self.assertEqual(prepared.status_code, 200)
        token = prepared.json()["certificate"]["token"]

        executed = self.client.post(
            f"/api/actions/admin/{token}/execute",
            headers={"Idempotency-Key": "api-create-orders"},
        )
        self.assertEqual(executed.status_code, 200)
        self.assertEqual(executed.json()["status"], "VERIFIED_SUCCESS")

    def test_role_and_schedule_preflight_are_available(self):
        role = self.client.post(
            "/api/intents/access/grant-role",
            json={
                "username": "alex",
                "role_name": "App.Reader",
                "role_reviewed": True,
            },
        )
        schedule = self.client.post(
            "/api/intents/task/17/schedule",
            json={
                "period": "Daily",
                "start_time": "03:00",
                "every": "1",
                "day": "",
            },
        )
        self.assertEqual(role.status_code, 200)
        self.assertEqual(schedule.status_code, 200)
        self.assertEqual(role.json()["plan_state"], "PLAN_READY")
        self.assertEqual(schedule.json()["plan_state"], "PLAN_READY")

    def test_authentication_boundary_and_operator_receipt(self):
        with patch.dict(os.environ, {"BATTERY_ACCESS_KEY": "a" * 40}):
            self.assertEqual(self.client.get("/api/catalog").status_code, 401)
            self.assertEqual(
                self.client.post(
                    "/api/session", json={"access_key": "wrong"}
                ).status_code,
                401,
            )
            login = self.client.post("/api/session", json={"access_key": "a" * 40})
            self.assertEqual(login.status_code, 200)
            self.assertIn("HttpOnly", login.headers["set-cookie"])
            self.assertEqual(self.client.get("/api/catalog").status_code, 200)
            self.assertEqual(
                self.client.post(
                    "/api/intents/task/17/run",
                    json={"task_definition_reviewed": True},
                    headers={"Origin": "https://unrelated.invalid"},
                ).status_code,
                403,
            )

    def test_receipt_detail_retains_actual_before_after_evidence(self):
        prepared = self.client.post(
            "/api/intents/task/17/run", json={"task_definition_reviewed": True}
        ).json()
        receipt = self.client.post(
            "/api/actions/task-run/" + prepared["certificate"]["token"] + "/execute",
            headers={"Idempotency-Key": "proof"},
        ).json()
        detail = self.client.get("/api/receipts/" + receipt["id"]).json()
        self.assertEqual(detail["receipt"]["operator"], "local-operator")
        self.assertEqual(len(detail["evidence"]), 4)
        self.assertTrue(detail["ledger"])
        self.assertNotIn(prepared["certificate"]["token"], str(detail))

    def test_demonstration_finding_resolves_only_after_verified_attempt(self):
        initial = self.client.get("/api/findings/demonstration").json()
        self.assertEqual(initial["scope"], "synthetic")
        self.assertEqual(initial["status"], "OPEN")
        self.assertEqual(initial["history_count"], 0)
        prepared = self.client.post(
            "/api/intents/task/17/run", json={"task_definition_reviewed": True}
        ).json()
        self.assertEqual(
            self.client.get("/api/findings/demonstration").json()["status"], "OPEN"
        )
        receipt = self.client.post(
            "/api/actions/task-run/" + prepared["certificate"]["token"] + "/execute",
            headers={"Idempotency-Key": "finding-run"},
        ).json()
        self.assertEqual(receipt["status"], "VERIFIED_SUCCESS")
        resolved = self.client.get("/api/findings/demonstration").json()
        self.assertEqual(resolved["status"], "RESOLVED")
        self.assertEqual(resolved["history_count"], 1)
        self.assertEqual(resolved["receipt_id"], receipt["id"])
        web.engine.adapter.history[17].clear()
        self.assertEqual(
            self.client.get("/api/findings/demonstration").json()["status"],
            "REVIEW",
        )

    def test_demonstration_finding_does_not_resolve_failed_attempt(self):
        web.engine = BatteryEngine(
            SyntheticTaskAdapter(run_result="failure"), ledger=Ledger()
        )
        prepared = self.client.post(
            "/api/intents/task/17/run", json={"task_definition_reviewed": True}
        ).json()
        receipt = self.client.post(
            "/api/actions/task-run/" + prepared["certificate"]["token"] + "/execute",
            headers={"Idempotency-Key": "failed-finding-run"},
        ).json()
        self.assertEqual(receipt["status"], "VERIFIED_FAILURE")
        self.assertEqual(
            self.client.get("/api/findings/demonstration").json()["status"],
            "REVIEW",
        )

    def test_health_does_not_claim_a_broken_chain_is_ready(self):
        web.engine.ledger.append("probe", {})
        web.engine.ledger.records[0]["digest"] = "tampered"
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json()["ok"])


if __name__ == "__main__":
    unittest.main()


class NativeApiBoundaryTests(unittest.TestCase):
    def setUp(self):
        web.engine = BatteryEngine(SyntheticTaskAdapter(), ledger=Ledger())
        self.client = TestClient(web.app)

    def test_disabled_native_service_explains_missing_connection(self):
        with patch.dict(os.environ, {"BATTERY_NATIVE_URL": "", "BATTERY_ACCESS_KEY": ""}):
            response = self.client.get("/api/cases")
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.json()["available"])

    def test_private_evidence_requires_separate_adapter_credential(self):
        with patch.dict(os.environ, {"BATTERY_ADAPTER_KEY": "k" * 40, "BATTERY_ACCESS_KEY": "a" * 40}):
            self.client.post("/api/session", json={"access_key": "a" * 40})
            self.assertEqual(self.client.get("/api/native-evidence/x?phase=FINAL").status_code, 401)
            self.assertEqual(self.client.get("/api/native-evidence/x?phase=FINAL", headers={"X-Battery-Adapter": "wrong"}).status_code, 401)
            self.assertEqual(self.client.get("/api/native-evidence/x?phase=FINAL", headers={"X-Battery-Adapter": "k" * 40}).status_code, 404)

    def test_case_routes_require_operator_login_and_same_origin(self):
        with patch.dict(os.environ, {"BATTERY_ACCESS_KEY": "a" * 40}):
            self.assertEqual(self.client.get("/api/cases").status_code, 401)
            self.assertEqual(self.client.post("/api/cases", json={"receipt_id": "x"}).status_code, 401)
            self.client.post("/api/session", json={"access_key": "a" * 40})
            self.assertEqual(self.client.post("/api/cases", json={"receipt_id": "x"}, headers={"Origin": "https://foreign.invalid"}).status_code, 403)

    def test_browser_cannot_supply_authoritative_native_observations(self):
        from unittest.mock import Mock
        bridge = Mock()
        bridge.submit.return_value = {"id": "case-1", "state": "QUEUED"}
        with patch.object(web, "native_cases", return_value=bridge), patch.dict(os.environ, {"BATTERY_ACCESS_KEY": ""}):
            response = self.client.post("/api/cases", json={"receipt_id": "receipt-1", "initial": {"available": True}, "contract": {"accept": "anything"}}, headers={"Idempotency-Key": "request-key-000001"})
            self.assertEqual(response.status_code, 200)
            bridge.submit.assert_called_once_with("receipt-1", "request-key-000001", "local-operator", "")
