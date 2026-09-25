"""Deterministic judging scenarios for Battery's safety claims."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Callable

from .ledger import Ledger
from .models import RuleValidation
from .task_slice import BatteryEngine, SyntheticTaskAdapter


class ScenarioClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.value

    def advance(self, seconds: int) -> None:
        self.value += timedelta(seconds=seconds)


def _engine(adapter=None, **options) -> BatteryEngine:
    return BatteryEngine(adapter or SyntheticTaskAdapter(), ledger=Ledger(), **options)


def _intentional_change() -> None:
    engine = _engine()
    plan = engine.prepare_create_web_app(
        name="/api/orders", namespace="USER", dispatch_class="Demo.Orders",
        resource="App.Reader", requested_by="judge",
    )
    receipt = engine.execute_admin(plan["certificate"]["token"], "scenario-create")
    assert receipt["status"] == "VERIFIED_SUCCESS"


def _insufficient_privilege() -> None:
    engine = _engine(SyntheticTaskAdapter(task_privilege=False, operate_privilege=False))
    plan = engine.prepare_task_run(17, requested_by="judge", task_definition_reviewed=True)
    assert plan["certificate"] is None and plan["finding"]["state"] == "BLOCKED"


def _failed_task_is_not_blindly_retried() -> None:
    engine = _engine(SyntheticTaskAdapter(prior_failure=True))
    plan = engine.prepare_task_run(17, requested_by="judge", task_definition_reviewed=True)
    assert plan["certificate"] is None
    assert "failure alone does not prove" in " ".join(plan["finding"]["missing_evidence"])


def _stale_evidence() -> None:
    clock = ScenarioClock()
    engine = _engine(now=clock)
    plan = engine.prepare_task_run(17, requested_by="judge", task_definition_reviewed=True)
    clock.advance(61)
    try:
        engine.execute_task_run(plan["certificate"]["token"], "scenario-stale")
    except ValueError as exc:
        assert "expired" in str(exc)
    else:
        raise AssertionError("expired evidence permitted execution")


def _ambiguous_transport_without_retry() -> None:
    adapter = SyntheticTaskAdapter(ambiguous=True)
    engine = _engine(adapter)
    plan = engine.prepare_task_run(17, requested_by="judge", task_definition_reviewed=True)
    token = plan["certificate"]["token"]
    first = engine.execute_task_run(token, "scenario-ambiguous")
    repeated = engine.execute_task_run(token, "scenario-ambiguous")
    assert first["status"] == "OUTCOME_UNKNOWN"
    assert repeated["id"] == first["id"] and adapter.run_calls == 1
    adapter.reveal_pending()
    assert engine.reconcile(first["id"])["status"] == "VERIFIED_SUCCESS"
    assert adapter.run_calls == 1


def _wrong_rule_stays_blocked() -> None:
    engine = _engine(rule_validation=RuleValidation.DRAFT)
    plan = engine.prepare_grant_role(
        username="alex", role_name="App.Reader", requested_by="judge", role_reviewed=True
    )
    assert plan["certificate"] is None
    assert "execution requires SIMULATED" in " ".join(plan["finding"]["missing_evidence"])


def _concurrent_change_invalidates_preflight() -> None:
    adapter = SyntheticTaskAdapter()
    engine = _engine(adapter)
    plan = engine.prepare_schedule_task(
        task_id=17, period="Daily", start_time="03:00", every="1", day="",
        requested_by="judge",
    )
    adapter.tasks[17]["Description"] = "changed concurrently"
    try:
        engine.execute_admin(plan["certificate"]["token"], "scenario-concurrent")
    except ValueError as exc:
        assert "changed after preflight" in str(exc)
    else:
        raise AssertionError("concurrent target change permitted execution")


def _sensitive_values_absent() -> None:
    engine = _engine()
    rendered = str(engine.observations()).casefold()
    assert "password" not in rendered and "private key" not in rendered
    assert engine.ledger.verify()


SCENARIOS: dict[str, Callable[[], None]] = {
    "intentional_change": _intentional_change,
    "insufficient_privilege": _insufficient_privilege,
    "failed_task_restraint": _failed_task_is_not_blindly_retried,
    "stale_evidence": _stale_evidence,
    "ambiguous_transport": _ambiguous_transport_without_retry,
    "wrong_rule_defense": _wrong_rule_stays_blocked,
    "concurrent_change": _concurrent_change_invalidates_preflight,
    "sensitive_values_absent": _sensitive_values_absent,
}


def run_scenarios() -> dict[str, object]:
    results = []
    for name, scenario in SCENARIOS.items():
        try:
            scenario()
        except Exception as exc:  # scenario report must include every case
            results.append({"name": name, "passed": False, "detail": str(exc)})
        else:
            results.append({"name": name, "passed": True, "detail": "proved"})
    return {
        "passed": sum(1 for item in results if item["passed"]),
        "total": len(results),
        "scenarios": results,
    }
