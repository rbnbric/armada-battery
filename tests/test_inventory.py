from __future__ import annotations

import unittest

from battery.errors import AdapterError
from battery.task_slice import IrisTaskAdapter


class StubIrisAdapter(IrisTaskAdapter):
    def __init__(self):
        super().__init__("http://iris.invalid/api/admin", "Basic never-sent")
        self.calls = []

    def _request(self, method, path, *, query=None, body=None):
        self.calls.append((method, path, query))
        if path == "/v1/security/ssl-configuration/":
            raise AdapterError("IRIS returned HTTP 403: forbidden")
        if path in {
            "/v1/process/",
            "/v1/security/audit/event/",
            "/v1/wallet/",
        }:
            return [{"Name": "synthetic"}]
        return {"Observed": True}


class RecordingIrisAdapter(IrisTaskAdapter):
    def __init__(self):
        super().__init__("http://iris.invalid/api/admin", "Basic never-sent")
        self.calls = []

    def _request(self, method, path, *, query=None, body=None):
        self.calls.append((method, path, query, body))
        if path == "/v1/task" and method == "GET":
            return {
                "Name": "Demo Task",
                "TaskClass": "Demo.Task",
                "TimePeriod": "On Demand",
            }
        if path == "/v1/task/info":
            return {
                "Name": "",
                "Suspended": False,
                "Status": "1",
                "Error": "Success",
            }
        if path == "/v1/task/history/":
            return [{"Task": 7, "LastStarted": "1", "Error": "Success"}]
        if path == "/v1/web-app":
            return {"Name": "/api/demo", "Namespace": "USER"}
        return []


class InventoryTests(unittest.TestCase):
    def test_inventory_is_bounded_and_one_denial_does_not_hide_other_areas(self):
        adapter = StubIrisAdapter()
        areas = adapter.get_portal_inventory()

        self.assertEqual(len(areas), 8)
        self.assertEqual(areas["tls"]["quality"], "FORBIDDEN")
        self.assertEqual(areas["processes"]["quality"], "VALID")
        self.assertEqual(areas["audit"]["quality"], "VALID")
        self.assertEqual(areas["databases"]["quality"], "UNAVAILABLE")
        self.assertEqual(areas["journals"]["quality"], "UNAVAILABLE")
        for method, _path, query in adapter.calls:
            self.assertEqual(method, "GET")
            if query and "maxRows" in query:
                self.assertLessEqual(query["maxRows"], 1000)


class V1PathTests(unittest.TestCase):
    def adapter(self) -> RecordingIrisAdapter:
        adapter = RecordingIrisAdapter()
        adapter.list_tasks()
        adapter.get_task(7)
        adapter.get_history(7)
        adapter.run_task(7)
        adapter.put_task(7, {"TimePeriod": "Daily"})
        adapter.list_web_apps()
        adapter.get_web_app("/api/demo")
        adapter.put_web_app("/api/demo", {"NameSpace": "USER", "Description": "demo"})
        adapter.list_users()
        adapter.get_user("alex")
        adapter.put_user("alex", {"Roles": ["App.Reader"]})
        adapter.list_roles()
        adapter.get_role("App.Reader")
        adapter.list_resources()
        return adapter

    def test_every_call_uses_the_v1_management_api(self):
        adapter = self.adapter()
        task = adapter.get_task(7)
        calls = {(method, path): query for method, path, query, _body in adapter.calls}

        self.assertIn(("GET", "/v1/task/"), calls)
        self.assertEqual(calls[("GET", "/v1/task/info")], {"id": 7})
        self.assertEqual(calls[("GET", "/v1/task")], {"id": 7})
        run = next(c for c in adapter.calls if c[:2] == ("POST", "/v1/task/run"))
        self.assertEqual(run[3], {"RunNow": True})
        self.assertEqual(
            calls[("GET", "/v1/task/history/")], {"id": 7, "name": "Demo Task"}
        )
        self.assertEqual(calls[("POST", "/v1/task/run")], {"id": 7})
        self.assertEqual(calls[("PUT", "/v1/task")], {"id": 7})
        self.assertIn(("GET", "/v1/web-app/"), calls)
        self.assertEqual(calls[("GET", "/v1/web-app")], {"name": "/api/demo"})
        self.assertEqual(calls[("PUT", "/v1/web-app")], {"name": "/api/demo"})
        self.assertIn(("GET", "/v1/security/user/"), calls)
        self.assertEqual(calls[("GET", "/v1/security/user")], {"name": "alex"})
        self.assertEqual(calls[("PUT", "/v1/security/user")], {"name": "alex"})
        self.assertIn(("GET", "/v1/security/role/"), calls)
        self.assertEqual(calls[("GET", "/v1/security/role")], {"name": "App.Reader"})
        self.assertIn(("GET", "/v1/security/resource/"), calls)
        self.assertFalse([path for _m, path, _q, _b in adapter.calls if "v2" in path])
        self.assertEqual(task["Name"], "Demo Task")
        self.assertEqual(task["Status"], "1")

    def test_history_rows_carry_the_engine_contract_keys(self):
        adapter = RecordingIrisAdapter()
        rows = adapter.get_history(7)
        fingerprint_keys = {
            "TaskId",
            "LastStart",
            "Completed",
            "LogDatetime",
            "Status",
            "Result",
        }
        self.assertTrue(fingerprint_keys <= set(rows[0]))
        self.assertEqual(rows[0]["TaskId"], 7)
        self.assertEqual(rows[0]["Result"], "Success")

    def test_web_app_namespace_spelling_is_bridged_both_ways(self):
        adapter = RecordingIrisAdapter()
        app = adapter.get_web_app("/api/demo")
        adapter.put_web_app("/api/demo", {"NameSpace": "USER"})
        body = adapter.calls[-1][3]
        self.assertEqual(app["NameSpace"], "USER")
        self.assertEqual(body.get("Namespace"), "USER")
        self.assertNotIn("NameSpace", body)


if __name__ == "__main__":
    unittest.main()
