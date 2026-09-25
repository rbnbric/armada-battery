from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

import importlib.util
import sys
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "armada_battery_app", Path(__file__).resolve().parents[1] / "app.py")
web = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = web
_spec.loader.exec_module(web)
from battery.ledger import Ledger
from battery.task_slice import BatteryEngine, SyntheticTaskAdapter


class ApiTests(unittest.TestCase):
    def setUp(self):
        web.engine = BatteryEngine(SyntheticTaskAdapter(), ledger=Ledger())
        self.client = TestClient(web.app)

    def test_catalog_and_security_headers(self):
        response = self.client.get("/api/catalog")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["namespaces"], ["USER"])
        self.assertIn("frame-ancestors 'none'", response.headers["content-security-policy"])

        observations = self.client.get("/api/observations").json()["areas"]
        self.assertEqual(len(observations), 8)
        self.assertTrue(all(item["quality"] == "VALID" for item in observations.values()))
        self.assertNotIn("secret value", str(observations).lower())

        assurance = self.client.get("/api/assurance").json()
        self.assertEqual((assurance["passed"], assurance["total"]), (8, 8))
        evidence = self.client.get("/api/evidence").json()
        self.assertTrue(evidence["valid"])

    def test_web_app_prepare_execute_and_readback(self):
        prepared = self.client.post("/api/intents/web-app/create", json={
            "name": "/api/orders",
            "namespace": "USER",
            "dispatch_class": "Demo.Orders",
            "resource": "App.Reader",
        })
        self.assertEqual(prepared.status_code, 200)
        token = prepared.json()["certificate"]["token"]

        executed = self.client.post(
            f"/api/actions/admin/{token}/execute",
            headers={"Idempotency-Key": "api-create-orders"},
        )
        self.assertEqual(executed.status_code, 200)
        self.assertEqual(executed.json()["status"], "VERIFIED_SUCCESS")

    def test_role_and_schedule_preflight_are_available(self):
        role = self.client.post("/api/intents/access/grant-role", json={
            "username": "alex", "role_name": "App.Reader",
            "role_reviewed": True,
        })
        schedule = self.client.post("/api/intents/task/17/schedule", json={
            "period": "Daily", "start_time": "03:00", "every": "1",
            "day": "",
        })
        self.assertEqual(role.status_code, 200)
        self.assertEqual(schedule.status_code, 200)
        self.assertEqual(role.json()["plan_state"], "PLAN_READY")
        self.assertEqual(schedule.json()["plan_state"], "PLAN_READY")


if __name__ == "__main__":
    unittest.main()
