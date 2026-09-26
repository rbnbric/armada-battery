"""Intent-to-verification scheduled-task vertical slice."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Protocol

from .admin_slice import AdministrativeIntentMixin
from .errors import AdapterError, AmbiguousTransport
from .ledger import Ledger, sanitize, serialized
from .models import (
    Finding,
    FindingState,
    Intent,
    IntentKind,
    Observation,
    PreflightCertificate,
    Receipt,
    ReceiptStatus,
    RuleSpec,
    RuleValidation,
    to_data,
)


class TaskAdapter(Protocol):
    synthetic: bool
    version: str

    def get_info(self) -> dict[str, Any]: ...
    def list_tasks(self) -> list[dict[str, Any]]: ...
    def get_task(self, task_id: int) -> dict[str, Any]: ...
    def get_history(self, task_id: int) -> list[dict[str, Any]]: ...
    def run_task(self, task_id: int) -> None: ...
    def put_task(self, task_id: int, payload: dict[str, Any]) -> None: ...
    def list_web_apps(self) -> list[dict[str, Any]]: ...
    def get_web_app(self, name: str) -> dict[str, Any]: ...
    def put_web_app(self, name: str, payload: dict[str, Any]) -> None: ...
    def list_users(self) -> list[dict[str, Any]]: ...
    def get_user(self, name: str) -> dict[str, Any]: ...
    def put_user(self, name: str, payload: dict[str, Any]) -> None: ...
    def list_roles(self) -> list[dict[str, Any]]: ...
    def get_role(self, name: str) -> dict[str, Any]: ...
    def list_resources(self) -> list[dict[str, Any]]: ...
    def get_portal_inventory(self) -> dict[str, dict[str, Any]]: ...


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode()).hexdigest()


def _history_fingerprint(row: dict[str, Any]) -> str:
    return _digest(
        {
            key: row.get(key)
            for key in (
                "TaskId",
                "LastStart",
                "Completed",
                "LogDatetime",
                "Status",
                "Result",
            )
        }
    )


_VALIDATION_ORDER = {
    RuleValidation.DRAFT: 0,
    RuleValidation.SIMULATED: 1,
    RuleValidation.LIVE_OBSERVED: 2,
    RuleValidation.APPROVED: 3,
}


class SyntheticTaskAdapter:
    synthetic = True
    version = "synthetic-v1"

    def __init__(
        self,
        *,
        task_privilege: bool = True,
        operate_privilege: bool = True,
        suspended: bool = False,
        prior_failure: bool = False,
        run_result: str = "success",
        ambiguous: bool = False,
    ) -> None:
        self.task_privilege = task_privilege
        self.operate_privilege = operate_privilege
        self.ambiguous = ambiguous
        self.run_result = run_result
        self.run_calls = 0
        self.tasks = {
            17: {
                "Id": 17,
                "Name": "Battery Demonstration Task",
                "Description": "Synthetic on-demand task with no external side effects",
                "TaskClass": "Battery.Demo.Task",
                "NameSpace": "USER",
                "TimePeriod": "On Demand",
                "Suspended": suspended,
                "Status": "1",
            }
        }
        self.history: dict[int, list[dict[str, Any]]] = {17: []}
        if prior_failure:
            self.history[17].append(
                {
                    "TaskId": 17,
                    "LastStart": "2026-09-22T10:00:00+00:00",
                    "Completed": "2026-09-22T10:00:02+00:00",
                    "LogDatetime": "2026-09-22T10:00:02+00:00",
                    "Status": "Failed",
                    "Result": "Synthetic failure",
                }
            )
        self.pending_history: list[dict[str, Any]] = []
        self.web_apps = {
            "/api/existing": {
                "Name": "/api/existing",
                "NameSpace": "USER",
                "Enabled": True,
                "Type": 2,
                "Resource": "App.Reader",
                "DispatchClass": "Demo.Existing",
            }
        }
        self.users = {
            "alex": {
                "Name": "alex",
                "FullName": "Alex Example",
                "Enabled": True,
                "Roles": [],
            }
        }
        self.roles = {
            "App.Reader": {
                "Name": "App.Reader",
                "Description": "Read the demonstration application",
                "GrantedRoles": [],
                "Resources": [{"Name": "App.Reader", "Permissions": "R"}],
            }
        }
        self.resources = [
            {
                "Name": "App.Reader",
                "Description": "Demonstration application",
                "PublicPermission": "",
            }
        ]

    def get_info(self) -> dict[str, Any]:
        return {
            "apiVersion": 2,
            "serverVersion": self.version,
            "username": "demo-operator",
            "systemMode": "DEVELOPMENT",
            "product": "iris",
            "namespaces": [{"name": "USER"}],
            "privileges": {
                "Task": {"use": self.task_privilege},
                "Operate": {"use": self.operate_privilege},
                "Secure": {"use": True},
            },
        }

    def list_tasks(self) -> list[dict[str, Any]]:
        return [dict(task) for task in self.tasks.values()]

    def get_task(self, task_id: int) -> dict[str, Any]:
        if task_id not in self.tasks:
            raise AdapterError(f"Task {task_id} does not exist")
        return dict(self.tasks[task_id])

    def get_history(self, task_id: int) -> list[dict[str, Any]]:
        return [dict(row) for row in self.history.get(task_id, [])]

    def run_task(self, task_id: int) -> None:
        self.run_calls += 1
        if task_id not in self.tasks:
            raise AdapterError(f"Task {task_id} does not exist")
        now = _utcnow().isoformat()
        success = self.run_result == "success"
        row = {
            "TaskId": task_id,
            "LastStart": now,
            "Completed": now,
            "LogDatetime": now,
            "Status": "Success" if success else "Failed",
            "Result": "Success" if success else "Synthetic execution failure",
        }
        if self.ambiguous:
            self.pending_history.append(row)
            raise AmbiguousTransport(
                "Connection ended before the response was received"
            )
        self.history.setdefault(task_id, []).append(row)

    def reveal_pending(self) -> None:
        for row in self.pending_history:
            self.history.setdefault(int(row["TaskId"]), []).append(row)
        self.pending_history.clear()

    def put_task(self, task_id: int, payload: dict[str, Any]) -> None:
        self.tasks[task_id].update(payload)

    def list_web_apps(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self.web_apps.values()]

    def get_web_app(self, name: str) -> dict[str, Any]:
        if name not in self.web_apps:
            raise AdapterError(f"Web application {name} does not exist")
        return dict(self.web_apps[name])

    def put_web_app(self, name: str, payload: dict[str, Any]) -> None:
        self.web_apps[name] = {"Name": name, **payload}

    def list_users(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self.users.values()]

    def get_user(self, name: str) -> dict[str, Any]:
        if name not in self.users:
            raise AdapterError(f"User {name} does not exist")
        return dict(self.users[name])

    def put_user(self, name: str, payload: dict[str, Any]) -> None:
        self.users[name].update(payload)

    def list_roles(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self.roles.values()]

    def get_role(self, name: str) -> dict[str, Any]:
        if name not in self.roles:
            raise AdapterError(f"Role {name} does not exist")
        return dict(self.roles[name])

    def list_resources(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self.resources]

    def get_portal_inventory(self) -> dict[str, dict[str, Any]]:
        return {
            "system": {
                "source": "GET /v1/monitor/dashboard/system-resources",
                "quality": "VALID",
                "summary": "CPU 7% · memory 34% · 259 GB storage available",
            },
            "processes": {
                "source": "GET /v1/process/",
                "quality": "VALID",
                "summary": "4 processes observed; none marked suspended",
            },
            "databases": {
                "source": "simulated database inventory (no IRIS v1 endpoint)",
                "quality": "VALID",
                "summary": "3 databases observed",
            },
            "license": {
                "source": "GET /v1/monitor/license-usage",
                "quality": "VALID",
                "summary": "Community license usage is observable",
            },
            "audit": {
                "source": "GET /v1/security/audit/enabled + /event/",
                "quality": "VALID",
                "summary": "Auditing enabled; 12 event definitions observed",
            },
            "journals": {
                "source": "simulated journal inventory (no IRIS v1 endpoint)",
                "quality": "VALID",
                "summary": "Journal settings and 2 recent files observed",
            },
            "tls": {
                "source": "GET /v1/security/ssl-configuration/",
                "quality": "VALID",
                "summary": "2 TLS configuration records observed; secret material omitted",
            },
            "wallets": {
                "source": "GET /v1/wallet/",
                "quality": "VALID",
                "summary": "1 wallet collection observed; sensitive payloads were not requested",
            },
        }


class IrisTaskAdapter:
    synthetic = False
    version = "iris-sysadmin-v1"

    _HISTORY_ALIASES = {
        "TaskId": ("TaskId", "Task", "Id"),
        "LastStart": ("LastStart", "LastStarted", "DisplayStarted", "StartTime"),
        "Completed": ("Completed", "LastFinished", "DisplayFinished", "EndTime"),
        "LogDatetime": ("LogDatetime", "DisplayLogDate", "LogDate"),
        "Status": ("DisplayStatus", "Status"),
        "Result": ("Result", "Error"),
    }

    def __init__(
        self, base_url: str, authorization: str, timeout: float = 15.0
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.authorization = authorization
        self.timeout = timeout

    @classmethod
    def from_environment(cls) -> "IrisTaskAdapter":
        base_url = os.environ["BATTERY_IRIS_URL"]
        bearer = os.environ.get("BATTERY_IRIS_BEARER")
        if bearer:
            authorization = f"Bearer {bearer}"
        else:
            user = os.environ.get("BATTERY_IRIS_USER", "")
            password = os.environ.get("BATTERY_IRIS_PASSWORD", "")
            if not user or not password:
                raise RuntimeError(
                    "IRIS user and password or bearer token are required"
                )
            token = base64.b64encode(f"{user}:{password}".encode()).decode()
            authorization = f"Basic {token}"
        return cls(base_url, authorization)

    def _request(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.base_url}/{path.lstrip('/')}"
        if query:
            url += "?" + urllib.parse.urlencode(query)
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={
                "Authorization": self.authorization,
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read(2 * 1024 * 1024 + 1)
                if len(raw) > 2 * 1024 * 1024:
                    error = (
                        AmbiguousTransport
                        if method in {"POST", "PUT", "DELETE", "PATCH"}
                        else AdapterError
                    )
                    raise error("IRIS response exceeded the 2 MiB collector limit")
        except urllib.error.HTTPError as exc:
            error = (
                AmbiguousTransport
                if method in {"POST", "PUT", "DELETE", "PATCH"} and exc.code >= 500
                else AdapterError
            )
            raise error(
                f"IRIS returned HTTP {exc.code}; upstream body withheld"
            ) from exc
        except (TimeoutError, urllib.error.URLError, ConnectionError) as exc:
            if method in {"POST", "PUT", "DELETE", "PATCH"}:
                raise AmbiguousTransport(str(exc)) from exc
            raise AdapterError(str(exc)) from exc
        try:
            payload = json.loads(raw or b"{}")
        except (ValueError, UnicodeError) as exc:
            error = (
                AmbiguousTransport
                if method in {"POST", "PUT", "DELETE", "PATCH"}
                else AdapterError
            )
            raise error("Malformed IRIS response; outcome not established") from exc
        if isinstance(payload, dict) and "result" in payload:
            return payload["result"]
        return payload

    def _task_name(self, task_id: int) -> str:
        name = self.get_task(task_id).get("Name")
        if not name:
            raise AdapterError(f"Task {task_id} has no observable Name")
        return str(name)

    @classmethod
    def _normalize_history_row(
        cls, row: dict[str, Any], task_id: int
    ) -> dict[str, Any]:
        normalized = dict(row)
        for target, sources in cls._HISTORY_ALIASES.items():
            if target == "Status" and row.get("DisplayStatus") not in (None, ""):
                normalized["Status"] = row["DisplayStatus"]
                continue
            if normalized.get(target) in (None, ""):
                for source in sources:
                    value = row.get(source)
                    if value not in (None, ""):
                        normalized[target] = value
                        break
        if not normalized.get("LogDatetime"):
            date, time = row.get("LogDate"), row.get("LogTime")
            if date and time:
                normalized["LogDatetime"] = f"{date} {time}"
        if normalized.get("TaskId") in (None, ""):
            normalized["TaskId"] = task_id
        for key in cls._HISTORY_ALIASES:
            normalized.setdefault(key, "")
        return normalized

    @staticmethod
    def _unavailable(detail: str) -> None:
        raise AdapterError(detail)

    def get_info(self) -> dict[str, Any]:
        return self._request("GET", "/info")

    def list_tasks(self) -> list[dict[str, Any]]:
        return self._request("GET", "/v1/task/")

    def get_task(self, task_id: int) -> dict[str, Any]:
        definition = self._request("GET", "/v1/task", query={"id": task_id})
        runtime = self._request("GET", "/v1/task/info", query={"id": task_id})
        if not isinstance(definition, dict) or not isinstance(runtime, dict):
            raise AdapterError("Malformed task definition or runtime information")
        # IRIS can return blank definition fields on the runtime-info surface.
        # Preserve the configured definition unless runtime contributes a real value.
        merged = dict(definition)
        merged.update(
            key_value
            for key_value in runtime.items()
            if key_value[1] not in (None, "") or key_value[0] not in merged
        )
        merged["Id"] = task_id
        return merged

    def get_history(self, task_id: int) -> list[dict[str, Any]]:
        rows = self._request(
            "GET",
            "/v1/task/history/",
            query={"id": task_id, "name": self._task_name(task_id)},
        )
        if isinstance(rows, dict):
            rows = next(
                (value for value in rows.values() if isinstance(value, list)), None
            )
        if not isinstance(rows, list):
            raise AdapterError(
                "Task history response did not contain a list of records"
            )
        return [self._normalize_history_row(row, task_id) for row in rows]

    def run_task(self, task_id: int) -> None:
        self._request(
            "POST", "/v1/task/run", query={"id": task_id}, body={"RunNow": True}
        )

    def put_task(self, task_id: int, payload: dict[str, Any]) -> None:
        self._request("PUT", "/v1/task", query={"id": task_id}, body=payload)

    def list_web_apps(self) -> list[dict[str, Any]]:
        return self._request("GET", "/v1/web-app/")

    def get_web_app(self, name: str) -> dict[str, Any]:
        app = self._request("GET", "/v1/web-app", query={"name": name})
        if isinstance(app, dict) and "NameSpace" not in app and "Namespace" in app:
            app = {**app, "NameSpace": app["Namespace"]}
        return app

    def put_web_app(self, name: str, payload: dict[str, Any]) -> None:
        body = dict(payload)
        if "NameSpace" in body and "Namespace" not in body:
            body["Namespace"] = body.pop("NameSpace")
        self._request("PUT", "/v1/web-app", query={"name": name}, body=body)

    def list_users(self) -> list[dict[str, Any]]:
        return self._request("GET", "/v1/security/user/")

    def get_user(self, name: str) -> dict[str, Any]:
        return self._request("GET", "/v1/security/user", query={"name": name})

    def put_user(self, name: str, payload: dict[str, Any]) -> None:
        self._request("PUT", "/v1/security/user", query={"name": name}, body=payload)

    def list_roles(self) -> list[dict[str, Any]]:
        return self._request("GET", "/v1/security/role/")

    def get_role(self, name: str) -> dict[str, Any]:
        return self._request("GET", "/v1/security/role", query={"name": name})

    def list_resources(self) -> list[dict[str, Any]]:
        return self._request("GET", "/v1/security/resource/")

    def get_portal_inventory(self) -> dict[str, dict[str, Any]]:
        requests = {
            "system": ("/v1/monitor/dashboard/system-resources", None),
            "processes": ("/v1/process/", None),
            "license": ("/v1/monitor/license-usage", None),
            "tls": ("/v1/security/ssl-configuration/", None),
            "wallets": ("/v1/wallet/", None),
        }
        result: dict[str, dict[str, Any]] = {}
        for area, (path, query) in requests.items():
            try:
                value = self._request("GET", path, query=query)
            except AdapterError as exc:
                result[area] = {
                    "source": f"GET {path}",
                    "quality": "FORBIDDEN" if "HTTP 403" in str(exc) else "UNAVAILABLE",
                    "summary": str(exc),
                }
                continue
            count = len(value) if isinstance(value, list) else None
            result[area] = {
                "source": f"GET {path}",
                "quality": "VALID",
                "captured_at": _utcnow().isoformat(),
                "count": count,
                "complete": None,
                "values": sanitize(value) if area in {"system", "license"} else None,
                "summary": (
                    f"{count} {'record' if count == 1 else 'records'} observed"
                    if count is not None
                    else "Current aggregate state observed"
                ),
            }
        compound = {
            "audit": (
                ("/v1/security/audit/enabled", None),
                ("/v1/security/audit/event/", None),
            ),
        }
        for area, calls in compound.items():
            values = []
            try:
                for path, query in calls:
                    values.append(self._request("GET", path, query=query))
            except AdapterError as exc:
                result[area] = {
                    "source": " + ".join(f"GET {path}" for path, _ in calls),
                    "quality": "FORBIDDEN" if "HTTP 403" in str(exc) else "UNAVAILABLE",
                    "summary": str(exc),
                }
                continue
            records = values[-1]
            count = len(records) if isinstance(records, list) else None
            result[area] = {
                "source": " + ".join(f"GET {path}" for path, _ in calls),
                "quality": "VALID",
                "summary": (
                    f"Settings and {count} records observed"
                    if count is not None
                    else "Current settings and records observed"
                ),
            }
        for area, detail in {
            "databases": "The IRIS v1 Management API exposes no database inventory endpoint",
            "journals": "The IRIS v1 Management API exposes no journal inventory endpoint",
        }.items():
            try:
                self._unavailable(detail)
            except AdapterError as exc:
                result[area] = {
                    "source": "IRIS v1 Management API",
                    "quality": "UNAVAILABLE",
                    "summary": str(exc),
                }
        return result


class BatteryEngine(AdministrativeIntentMixin):
    """One complete, bounded management workflow for an existing task."""

    def __init__(
        self,
        adapter: TaskAdapter,
        *,
        ledger: Ledger | None = None,
        allow_changes: bool = True,
        rule_validation: RuleValidation | None = None,
        now: Any = _utcnow,
    ) -> None:
        self.adapter = adapter
        self.ledger = ledger or Ledger()
        self.allow_changes = allow_changes
        self.now = now
        validation = rule_validation or (
            RuleValidation.SIMULATED if adapter.synthetic else RuleValidation.DRAFT
        )
        minimum = (
            RuleValidation.SIMULATED
            if adapter.synthetic
            else RuleValidation.LIVE_OBSERVED
        )
        self.rule = RuleSpec(
            id="task.intent.run-existing",
            version=1,
            rationale=(
                "The operator requested a new run. The public SysAdmin API exposes a run "
                "operation and task history suitable for independent readback."
            ),
            assumptions=(
                "The selected task definition is the operator's intended target.",
                "The task is not suspended or already running.",
                "The operator has reviewed the task definition and its side effects.",
                "A new history row represents this attempt.",
            ),
            supported_versions=("synthetic-v1", "IRIS SysAdmin API v1"),
            contradictors=(
                "The task is suspended or already running.",
                "Required Task or Operate privilege is absent.",
                "The latest run failed and no failure-specific retry rule is validated.",
            ),
            counterexamples=(
                "A task can have irreversible external side effects invisible to Battery.",
                "Another administrator can change the task after preflight.",
                "A lost response can leave execution outcome ambiguous.",
            ),
            synthetic_tests=(
                "intent_without_incident",
                "prior_failure_does_not_imply_retry",
                "missing_privilege_blocks",
                "ambiguous_transport_does_not_retry",
            ),
            live_validations=(),
            validation=validation,
            minimum_execution_validation=minimum,
        )
        self.certificates: dict[str, PreflightCertificate] = {}
        self.receipts: dict[str, Receipt] = {}
        self.idempotency: dict[str, str] = {}
        self._initialize_admin()
        with self.ledger.locked():
            self._restore_runtime()

    def _restore_runtime(self):
        self.certificates = {}
        self.admin_certificates = {}
        self.receipts = {}
        self.idempotency = {}
        for record in self.ledger.records:
            data = dict(record["payload"])
            if record["event_type"] == "preflight_issued":
                key = data.get("certificate_digest")
                if not key:
                    continue  # Legacy authorizations are deliberately invalidated.
                if data["action_id"] == "task.run-once":
                    data.pop("certificate_digest", None)
                    data["token"] = key
                    for field in ("issued_at", "expires_at"):
                        data[field] = datetime.fromisoformat(data[field])
                    self.certificates[key] = PreflightCertificate(**data)
                else:
                    self.admin_certificates[key] = data
            elif (
                record["event_type"].startswith("action_") and "idempotency_key" in data
            ):
                for field in ("started_at", "finished_at", "verification_deadline"):
                    if data.get(field):
                        data[field] = datetime.fromisoformat(data[field])
                data["status"] = ReceiptStatus(data["status"])
                receipt = Receipt(**data)
                if record["event_type"] == "action_attempted":
                    receipt.status = ReceiptStatus.OUTCOME_UNKNOWN
                    receipt.explanation = "Dispatch was reserved durably. Its outcome is unresolved; reconcile without resending."
                self.receipts[receipt.id] = receipt
                scope = "task-run" if receipt.action_id == "task.run-once" else "admin"
                self.idempotency[f"{scope}:{receipt.idempotency_key}"] = receipt.id
        for receipt in self.receipts.values():
            for cert in self.certificates.values():
                if cert.intent_id == receipt.intent_id:
                    cert.used = True
            for cert in self.admin_certificates.values():
                if cert["intent_id"] == receipt.intent_id:
                    cert["used"] = True

    def _repeat(self, scope, token, operator):
        receipt = self.receipts[self.idempotency[scope]]
        if receipt.certificate_digest != _digest(token) or (
            operator is not None and receipt.operator != operator
        ):
            raise ValueError(
                "Execution key is already bound to another plan or operator"
            )
        return to_data(receipt)

    def _observe(self, source, target, value):
        data = to_data(
            Observation(
                str(uuid.uuid4()),
                source,
                target,
                self.now(),
                self.now() + timedelta(seconds=60),
                sanitize(value),
            )
        )
        self.ledger.append("observation", data)
        return data

    @serialized
    def list_receipts(self, operator=None, execution_key=None):
        return [
            to_data(r)
            for r in sorted(
                self.receipts.values(), key=lambda r: r.started_at, reverse=True
            )
            if (operator is None or r.operator == operator)
            and (execution_key is None or r.idempotency_key == execution_key)
        ][:100]

    @serialized
    def get_receipt(self, receipt_id, operator=None):
        receipt = self.receipts[receipt_id]
        if operator is not None and receipt.operator != operator:
            raise KeyError(receipt_id)
        return to_data(receipt)

    def dashboard(self) -> dict[str, Any]:
        info = self.adapter.get_info()
        tasks = self.adapter.list_tasks()
        return {
            "captured_at": self.now().isoformat(),
            "mode": "synthetic" if self.adapter.synthetic else "iris",
            "changes_enabled": self.allow_changes,
            "server": {
                "version": info.get("serverVersion"),
                "username": info.get("username"),
                "system_mode": info.get("systemMode"),
            },
            "tasks": sanitize(tasks),
            "rule": to_data(self.rule),
            "ledger_valid": self.ledger.verify(),
        }

    def observations(self) -> dict[str, Any]:
        areas = self.adapter.get_portal_inventory()
        captured = self.now().isoformat()
        for area in areas.values():
            area.setdefault("captured_at", captured)
            area.setdefault("freshness_seconds", 60)
            area.setdefault("complete", None)
        return {"captured_at": captured, "areas": sanitize(areas)}

    def audit_trail(self, limit: int = 20) -> dict[str, Any]:
        with self.ledger.locked():
            records = []
            for record in self.ledger.records[-max(1, min(limit, 100)) :]:
                payload = record.get("payload", {})
                records.append(
                    {
                        **record,
                        "target": payload.get("target"),
                        "status": payload.get("status") or payload.get("state"),
                    }
                )
            return {
                "valid": self.ledger.verify(),
                "count": len(self.ledger.records),
                "head": self.ledger.records[-1]["digest"]
                if self.ledger.records
                else None,
                "records": sanitize(records),
            }

    @serialized
    def prepare_task_run(
        self,
        task_id: int,
        *,
        requested_by: str,
        task_definition_reviewed: bool,
    ) -> dict[str, Any]:
        evaluated_at = self.now()
        intent = Intent(
            id=str(uuid.uuid4()),
            kind=IntentKind.RUN,
            target=f"task:{task_id}",
            desired_outcome="A new terminal history row exists for the requested task run.",
            constraints={"task_definition_reviewed": task_definition_reviewed},
            requested_by=requested_by,
            requested_at=evaluated_at,
            expires_at=evaluated_at + timedelta(minutes=5),
        )
        info = self.adapter.get_info()
        task = self.adapter.get_task(task_id)
        history = self.adapter.get_history(task_id)
        expires = evaluated_at + timedelta(seconds=60)
        observations = (
            Observation(
                str(uuid.uuid4()), "GET /info", "server", evaluated_at, expires, info
            ),
            Observation(
                str(uuid.uuid4()),
                "GET /v1/task/info",
                intent.target,
                evaluated_at,
                expires,
                task,
            ),
            Observation(
                str(uuid.uuid4()),
                "GET /v1/task/history/",
                intent.target,
                evaluated_at,
                expires,
                history,
                complete=True,
            ),
        )
        for observation in observations:
            self.ledger.append("observation", to_data(observation))
        self.ledger.append("intent_created", to_data(intent))

        privileges = info.get("privileges", {})
        blockers: list[str] = []
        alternatives: list[str] = []
        if not privileges.get("Task", {}).get("use", False):
            blockers.append("The authenticated user lacks %Admin_Task:U.")
        if not privileges.get("Operate", {}).get("use", False):
            blockers.append("Task history verification requires %Admin_Operate:U.")
        if task.get("Suspended") is True:
            blockers.append("The selected task is suspended.")
            alternatives.append("Review and resume the task before requesting a run.")
        if str(task.get("Status", "")).strip() == "-1":
            blockers.append("The selected task is already running.")
        if not task_definition_reviewed:
            blockers.append(
                "The task definition and its side effects have not been reviewed."
            )
        latest = self._latest_history(history)
        if latest and self._history_outcome(latest) == "unknown":
            blockers.append(
                "Latest task history has no recognized terminal outcome. Inspect it before requesting another run."
            )
        if latest and self._history_outcome(latest) == "failure":
            blockers.append(
                "The latest run failed; failure alone does not prove that retrying is correct."
            )
            alternatives.append(
                "Inspect the previous failure and validate a cause-specific remedy."
            )
        if (
            _VALIDATION_ORDER[self.rule.validation]
            < _VALIDATION_ORDER[self.rule.minimum_execution_validation]
        ):
            blockers.append(
                f"Rule validation is {self.rule.validation.value}; execution requires "
                f"{self.rule.minimum_execution_validation.value}."
            )
        if not self.allow_changes:
            blockers.append("Live state changes are disabled by server configuration.")

        state = FindingState.BLOCKED if blockers else FindingState.SAFE
        finding = Finding(
            id=str(uuid.uuid4()),
            rule_id=self.rule.id,
            rule_version=self.rule.version,
            target=intent.target,
            state=state,
            summary=(
                "The requested task run is prepared."
                if not blockers
                else "The requested task run needs attention before execution."
            ),
            consequence=(
                "Execution may create the task's declared and external side effects."
            ),
            evidence_ids=tuple(item.id for item in observations),
            missing_evidence=tuple(blockers),
            recommended_actions=(
                ("Run once and verify",)
                if not blockers
                else tuple(alternatives or ["Resolve blockers"])
            ),
            evaluated_at=evaluated_at,
            inference="configured policy applied to current task, privilege, and history observations",
        )
        self.ledger.append("finding_evaluated", to_data(finding))

        certificate = None
        if not blockers:
            token = secrets.token_urlsafe(24)
            fingerprints = tuple(_history_fingerprint(row) for row in history)
            evidence_digest = _digest(
                {
                    "task": task,
                    "task_privilege": privileges.get("Task"),
                    "operate_privilege": privileges.get("Operate"),
                }
            )
            cert = PreflightCertificate(
                token=token,
                intent_id=intent.id,
                action_id="task.run-once",
                target=intent.target,
                operator=requested_by,
                issued_at=evaluated_at,
                expires_at=expires,
                evidence_digest=evidence_digest,
                history_fingerprints=fingerprints,
                evidence_ids=tuple(item.id for item in observations),
            )
            self.certificates[_digest(token)] = cert
            certificate = to_data(cert)
            self.ledger.append(
                "preflight_issued",
                {
                    **certificate,
                    "token": "[REDACTED]",
                    "certificate_digest": _digest(token),
                },
            )

        return {
            "intent": to_data(intent),
            "finding": to_data(finding),
            "rule": to_data(self.rule),
            "task": sanitize(task),
            "history": sanitize(history),
            "certificate": certificate,
        }

    @serialized
    def execute_task_run(
        self, token: str, idempotency_key: str, operator: str | None = None
    ) -> dict[str, Any]:
        idempotency_scope = f"task-run:{idempotency_key}"
        if idempotency_scope in self.idempotency:
            return self._repeat(idempotency_scope, token, operator)
        cert = self.certificates.get(_digest(token))
        if not cert:
            raise ValueError("Unknown preflight certificate")
        if operator is not None and operator != cert.operator:
            raise ValueError("Preflight belongs to another operator")
        if cert.used:
            raise ValueError("Preflight certificate has already been used")
        if self.now() > cert.expires_at:
            raise ValueError("Preflight evidence has expired")
        task_id = int(cert.target.split(":", 1)[1])
        info = self.adapter.get_info()
        task = self.adapter.get_task(task_id)
        privileges = info.get("privileges", {})
        current_digest = _digest(
            {
                "task": task,
                "task_privilege": privileges.get("Task"),
                "operate_privilege": privileges.get("Operate"),
            }
        )
        if current_digest != cert.evidence_digest:
            raise ValueError(
                "Target or privileges changed after preflight; prepare again"
            )
        if not self.allow_changes:
            raise ValueError("Changes are disabled")
        if self.now() > cert.expires_at:
            raise ValueError("Preflight evidence expired during refresh")
        cert.used = True
        receipt = Receipt(
            id=str(uuid.uuid4()),
            intent_id=cert.intent_id,
            action_id=cert.action_id,
            target=cert.target,
            operator=cert.operator,
            idempotency_key=idempotency_key,
            started_at=self.now(),
            status=ReceiptStatus.EXECUTED_UNVERIFIED,
            before_evidence=cert.evidence_ids,
            history_before=cert.history_fingerprints,
            certificate_digest=_digest(token),
            verification_deadline=self.now() + timedelta(minutes=5),
            explanation="Attempt recorded before sending the IRIS request.",
        )
        self.receipts[receipt.id] = receipt
        self.idempotency[idempotency_scope] = receipt.id
        self.ledger.append("action_attempted", to_data(receipt))
        try:
            self.adapter.run_task(task_id)
            receipt.transport_result = "IRIS accepted the run request"
        except AmbiguousTransport as exc:
            receipt.status = ReceiptStatus.OUTCOME_UNKNOWN
            receipt.transport_result = "response unavailable"
            receipt.explanation = (
                "The request may have reached IRIS. Battery will not retry it automatically. "
                f"Transport detail: {exc}"
            )
            self.ledger.append("action_outcome_unknown", to_data(receipt))
            return to_data(receipt)
        except AdapterError as exc:
            receipt.status = ReceiptStatus.VERIFIED_FAILURE
            receipt.transport_result = "IRIS rejected or failed the request"
            receipt.explanation = str(exc)
            receipt.finished_at = self.now()
            self.ledger.append("action_failed", to_data(receipt))
            return to_data(receipt)
        return self._reconcile(receipt, task_id)

    @serialized
    def reconcile(self, receipt_id: str, operator: str | None = None) -> dict[str, Any]:
        receipt = self.receipts[receipt_id]
        if operator is not None and operator != receipt.operator:
            raise ValueError("Receipt belongs to another operator")
        if receipt.status in {
            ReceiptStatus.VERIFIED_SUCCESS,
            ReceiptStatus.VERIFIED_FAILURE,
        }:
            return to_data(receipt)
        if receipt.action_id != "task.run-once":
            return self.reconcile_admin(receipt)
        task_id = int(receipt.target.split(":", 1)[1])
        return self._reconcile(receipt, task_id)

    def _reconcile(self, receipt: Receipt, task_id: int) -> dict[str, Any]:
        try:
            history = self.adapter.get_history(task_id)
        except AdapterError:
            receipt.status = ReceiptStatus.OUTCOME_UNKNOWN
            receipt.explanation = (
                "Fresh task history is unavailable. The attempt will not be resent."
            )
        else:
            before = set(receipt.history_before)
            candidates = [r for r in history if _history_fingerprint(r) not in before]
            observation = self._observe("task-history", receipt.target, history)
            receipt.after_evidence = (observation["id"],)
            # IRIS v1 does not return an execution identifier from run-now. Time
            # proximity is insufficient to attribute a scheduled/other-user run.
            if not self.adapter.synthetic:
                receipt.status = (
                    ReceiptStatus.EXECUTED_UNVERIFIED
                    if receipt.transport_result == "IRIS accepted the run request"
                    else ReceiptStatus.OUTCOME_UNKNOWN
                )
                receipt.explanation = "Fresh history collected, but IRIS v1 supplies no attempt correlation identifier. These rows cannot independently prove this run. No automatic retry."
            else:
                candidates = [
                    r
                    for r in candidates
                    if str(r.get("TaskId")) == str(task_id)
                    and self._after_attempt(r, receipt.started_at)
                ]
                outcome = (
                    self._history_outcome(candidates[0])
                    if len(candidates) == 1
                    else "unknown"
                )
                if outcome in {"success", "failure"}:
                    receipt.status = (
                        ReceiptStatus.VERIFIED_SUCCESS
                        if outcome == "success"
                        else ReceiptStatus.VERIFIED_FAILURE
                    )
                    receipt.finished_at = self.now()
                    receipt.explanation = "The isolated synthetic adapter's new terminal record establishes the outcome."
                else:
                    receipt.status = (
                        ReceiptStatus.OUTCOME_UNKNOWN
                        if receipt.status == ReceiptStatus.OUTCOME_UNKNOWN
                        else ReceiptStatus.EXECUTED_UNVERIFIED
                    )
                    receipt.explanation = "No unique terminal record attributable to this attempt. Reconcile from fresh evidence; do not repeat the change."
        self.ledger.append("action_reconciled", to_data(receipt))
        return to_data(receipt)

    @staticmethod
    def _after_attempt(row, started_at):
        try:
            observed = datetime.fromisoformat(
                str(row.get("LastStart", "")).replace("Z", "+00:00")
            )
            return observed.tzinfo is not None and observed >= started_at
        except ValueError:
            return False

    @staticmethod
    def _history_outcome(row: dict[str, Any]) -> str:
        values = {
            str(row.get(key, "")).strip().casefold() for key in ("Status", "Result")
        }
        if values & {
            "failed",
            "failure",
            "error",
            "unsuccessful",
            "-2",
            "-3",
            "-4",
            "-5",
        }:
            return "failure"
        if values & {"incomplete", "not completed", "running", "pending"}:
            return "unknown"
        if values & {"success", "succeeded", "completed", "complete"}:
            return "success"
        return "unknown"

    @staticmethod
    def _latest_history(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not rows:
            return None
        return max(
            rows,
            key=lambda row: str(
                row.get("LogDatetime")
                or row.get("Completed")
                or row.get("LastStart")
                or ""
            ).replace("T", " "),
        )


def engine_from_environment() -> BatteryEngine:
    if os.environ.get("BATTERY_IRIS_URL"):
        adapter: TaskAdapter = IrisTaskAdapter.from_environment()
        allowed = os.environ.get("BATTERY_ALLOW_CHANGES", "").casefold() == "true"
        if allowed and len(os.environ.get("BATTERY_ACCESS_KEY", "")) < 32:
            raise RuntimeError(
                "Live changes require BATTERY_ACCESS_KEY of at least 32 characters"
            )
        validation_name = os.environ.get(
            "BATTERY_RULE_VALIDATION",
            os.environ.get("BATTERY_TASK_RULE_VALIDATION", "DRAFT"),
        )
        validation = RuleValidation(validation_name)
    else:
        adapter = SyntheticTaskAdapter()
        allowed = True
        validation = RuleValidation.SIMULATED
    ledger_path = Path(os.environ.get("BATTERY_LEDGER_PATH", "var/ledger.jsonl"))
    return BatteryEngine(
        adapter,
        ledger=Ledger(ledger_path),
        allow_changes=allowed,
        rule_validation=validation,
    )
