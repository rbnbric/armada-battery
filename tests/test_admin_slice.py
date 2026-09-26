from __future__ import annotations

import unittest

from battery.errors import AmbiguousTransport
from battery.ledger import Ledger
from battery.models import RuleValidation
from battery.task_slice import BatteryEngine, SyntheticTaskAdapter


class AmbiguousWebAppAdapter(SyntheticTaskAdapter):
    def put_web_app(self, name, payload):
        super().put_web_app(name, payload)
        raise AmbiguousTransport("response lost after commit")


class DeferredWebAppAdapter(SyntheticTaskAdapter):
    def __init__(self):
        super().__init__()
        self.pending = None

    def put_web_app(self, name, payload):
        self.pending = (name, payload)
        raise AmbiguousTransport("response lost before outcome was observable")

    def reveal_pending(self):
        name, payload = self.pending
        super().put_web_app(name, payload)


class AdminSliceTests(unittest.TestCase):
    def engine(self, adapter=None, **kwargs):
        return BatteryEngine(
            adapter or SyntheticTaskAdapter(), ledger=Ledger(), **kwargs
        )

    def test_create_web_app_executes_and_verifies(self):
        engine = self.engine()
        plan = engine.prepare_create_web_app(
            name="/api/orders",
            namespace="USER",
            dispatch_class="Demo.Orders",
            resource="App.Reader",
            requested_by="operator",
        )

        self.assertEqual(plan["plan_state"], "PLAN_READY")
        receipt = engine.execute_admin(plan["certificate"]["token"], "create-orders")
        self.assertEqual(receipt["status"], "VERIFIED_SUCCESS")
        self.assertEqual(
            engine.adapter.get_web_app("/api/orders")["DispatchClass"], "Demo.Orders"
        )

    def test_duplicate_web_app_is_blocked_without_overwrite(self):
        engine = self.engine()
        plan = engine.prepare_create_web_app(
            name="/api/existing",
            namespace="USER",
            dispatch_class="Different.Class",
            resource="App.Reader",
            requested_by="operator",
        )

        self.assertEqual(plan["plan_state"], "NEEDS_EVIDENCE")
        self.assertIsNone(plan["certificate"])
        self.assertIn("already exists", " ".join(plan["finding"]["missing_evidence"]))

    def test_grant_reviewed_role_preserves_existing_roles(self):
        adapter = SyntheticTaskAdapter()
        adapter.roles["Audit.Reader"] = {
            "Name": "Audit.Reader",
            "GrantedRoles": [],
            "Resources": [{"Name": "App.Reader", "Permissions": "R"}],
        }
        adapter.users["alex"]["Roles"] = ["Audit.Reader"]
        engine = self.engine(adapter)
        plan = engine.prepare_grant_role(
            username="alex",
            role_name="App.Reader",
            requested_by="operator",
            role_reviewed=True,
        )

        self.assertEqual(plan["plan_state"], "PLAN_READY")
        receipt = engine.execute_admin(plan["certificate"]["token"], "grant-reader")
        self.assertEqual(receipt["status"], "VERIFIED_SUCCESS")
        self.assertEqual(
            adapter.get_user("alex")["Roles"], ["App.Reader", "Audit.Reader"]
        )

    def test_role_grant_needs_review_and_never_automates_all(self):
        adapter = SyntheticTaskAdapter()
        adapter.roles["%All"] = {"Name": "%All", "GrantedRoles": [], "Resources": []}
        engine = self.engine(adapter)
        plan = engine.prepare_grant_role(
            username="alex",
            role_name="%All",
            requested_by="operator",
            role_reviewed=False,
        )

        blockers = " ".join(plan["finding"]["missing_evidence"])
        self.assertIn("not been reviewed", blockers)
        self.assertIn("does not automate", blockers)
        self.assertIsNone(plan["certificate"])

    def test_existing_role_is_satisfied_without_action(self):
        adapter = SyntheticTaskAdapter()
        adapter.users["alex"]["Roles"] = ["App.Reader"]
        engine = self.engine(adapter)
        plan = engine.prepare_grant_role(
            username="alex",
            role_name="App.Reader",
            requested_by="operator",
            role_reviewed=True,
        )

        self.assertEqual(plan["plan_state"], "SATISFIED")
        self.assertIsNone(plan["certificate"])
        self.assertTrue(engine.ledger.verify())

    def test_schedule_existing_task_executes_and_verifies(self):
        engine = self.engine()
        plan = engine.prepare_schedule_task(
            task_id=17,
            period="Weekly",
            start_time="02:30",
            every="1",
            day="27",
            requested_by="operator",
        )

        self.assertEqual(plan["plan_state"], "PLAN_READY")
        receipt = engine.execute_admin(plan["certificate"]["token"], "schedule-weekly")
        self.assertEqual(receipt["status"], "VERIFIED_SUCCESS")
        self.assertEqual(engine.adapter.get_task(17)["TimePeriodDay"], "27")

    def test_invalid_schedule_is_blocked(self):
        engine = self.engine()
        plan = engine.prepare_schedule_task(
            task_id=17,
            period="Weekly",
            start_time="25:90",
            every="0",
            day="08",
            requested_by="operator",
        )

        blockers = " ".join(plan["finding"]["missing_evidence"])
        self.assertIn("24-hour", blockers)
        self.assertIn("digits 1 through 7", blockers)
        self.assertIn("between 1 and 5", blockers)

    def test_invalid_monthly_schedule_is_blocked(self):
        engine = self.engine()
        plan = engine.prepare_schedule_task(
            task_id=17,
            period="Monthly",
            start_time="02:30",
            every="13",
            day="32",
            requested_by="operator",
        )
        blockers = " ".join(plan["finding"]["missing_evidence"])
        self.assertIn("between 1 and 12", blockers)
        self.assertIn("between 1 and 31", blockers)

    def test_draft_rule_cannot_execute(self):
        engine = self.engine(rule_validation=RuleValidation.DRAFT)
        plan = engine.prepare_create_web_app(
            name="/api/orders",
            namespace="USER",
            dispatch_class="Demo.Orders",
            resource="App.Reader",
            requested_by="operator",
        )
        self.assertEqual(plan["plan_state"], "NEEDS_EVIDENCE")
        self.assertIn(
            "execution requires SIMULATED",
            " ".join(plan["finding"]["missing_evidence"]),
        )

    def test_changed_target_or_authority_invalidates_preflight(self):
        adapter = SyntheticTaskAdapter()
        engine = self.engine(adapter)
        plan = engine.prepare_grant_role(
            username="alex",
            role_name="App.Reader",
            requested_by="operator",
            role_reviewed=True,
        )
        adapter.users["alex"]["FullName"] = "Changed after preflight"

        with self.assertRaisesRegex(ValueError, "changed after preflight"):
            engine.execute_admin(plan["certificate"]["token"], "stale-grant")

    def test_lost_response_can_be_proven_by_readback(self):
        engine = self.engine(AmbiguousWebAppAdapter())
        plan = engine.prepare_create_web_app(
            name="/api/orders",
            namespace="USER",
            dispatch_class="Demo.Orders",
            resource="App.Reader",
            requested_by="operator",
        )
        receipt = engine.execute_admin(plan["certificate"]["token"], "ambiguous-create")
        self.assertEqual(receipt["status"], "VERIFIED_SUCCESS")

    def test_ambiguous_admin_mutation_reconciles_without_retry(self):
        adapter = DeferredWebAppAdapter()
        engine = self.engine(adapter)
        plan = engine.prepare_create_web_app(
            name="/api/orders",
            namespace="USER",
            dispatch_class="Demo.Orders",
            resource="App.Reader",
            requested_by="operator",
        )
        receipt = engine.execute_admin(plan["certificate"]["token"], "deferred-create")
        self.assertEqual(receipt["status"], "OUTCOME_UNKNOWN")
        adapter.reveal_pending()
        reconciled = engine.reconcile(receipt["id"])
        self.assertEqual(reconciled["status"], "VERIFIED_SUCCESS")


if __name__ == "__main__":
    unittest.main()
