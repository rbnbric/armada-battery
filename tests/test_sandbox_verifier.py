from __future__ import annotations

from scripts.verify_sandbox import CORE_TEST_FILES, build_report


def test_sandbox_verifier_covers_the_dependency_free_engine_suite():
    assert CORE_TEST_FILES == (
        "test_task_slice.py",
        "test_admin_slice.py",
        "test_inventory.py",
        "test_scenarios.py",
        "test_runtime_safety.py",
    )
    report = build_report()
    assert report["passed"] is True
    assert report["core"]["tests_run"] == 39
    assert report["scenarios"]["passed"] == report["scenarios"]["total"] == 8
    assert set(report["excluded"]) == {"tests/test_api.py"}
