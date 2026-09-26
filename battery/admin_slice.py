"""Intent planning for ordinary IRIS administration outcomes."""

from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from datetime import timedelta
from typing import Any

from .errors import AdapterError, AmbiguousTransport
from .ledger import sanitize, serialized
from .models import (
    Finding,
    FindingState,
    Intent,
    IntentKind,
    Receipt,
    ReceiptStatus,
    RuleSpec,
    RuleValidation,
    to_data,
)


_ORDER = {
    RuleValidation.DRAFT: 0,
    RuleValidation.SIMULATED: 1,
    RuleValidation.LIVE_OBSERVED: 2,
    RuleValidation.APPROVED: 3,
}


def _digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode()).hexdigest()


class AdministrativeIntentMixin:
    """Mixed into BatteryEngine so all flows share one ledger and receipt store."""

    def _initialize_admin(self) -> None:
        self.admin_certificates: dict[str, dict[str, Any]] = {}

    def admin_catalog(self) -> dict[str, Any]:
        result = {"quality": {}}
        collectors = {
            "namespaces": lambda: [
                item.get("name")
                for item in self.adapter.get_info().get("namespaces", [])
            ],
            "web_apps": self.adapter.list_web_apps,
            "users": self.adapter.list_users,
            "roles": self.adapter.list_roles,
            "resources": self.adapter.list_resources,
            "tasks": self.adapter.list_tasks,
        }
        for name, collect in collectors.items():
            try:
                result[name] = sanitize(collect())
                result["quality"][name] = {
                    "quality": "VALID",
                    "captured_at": self.now().isoformat(),
                }
            except AdapterError as exc:
                result[name] = []
                result["quality"][name] = {
                    "quality": "FORBIDDEN" if "403" in str(exc) else "UNAVAILABLE",
                    "detail": sanitize(str(exc)),
                    "captured_at": self.now().isoformat(),
                }
        return result

    @serialized
    def prepare_create_web_app(
        self,
        *,
        name: str,
        namespace: str,
        dispatch_class: str,
        resource: str,
        requested_by: str,
    ) -> dict[str, Any]:
        now = self.now()
        intent = Intent(
            id=str(uuid.uuid4()),
            kind=IntentKind.CREATE,
            target=f"web-app:{name}",
            desired_outcome="A REST web application exists with the requested bounded configuration.",
            constraints={
                "namespace": namespace,
                "dispatch_class": dispatch_class,
                "resource": resource,
            },
            requested_by=requested_by,
            requested_at=now,
            expires_at=now + timedelta(minutes=5),
        )
        rule = self._admin_rule("web-app.create")
        info = self.adapter.get_info()
        apps = self.adapter.list_web_apps()
        resources = self.adapter.list_resources()
        namespaces = {
            item.get("name") for item in info.get("namespaces", []) if item.get("name")
        }
        blockers: list[str] = []
        if not info.get("privileges", {}).get("Secure", {}).get("use", False):
            blockers.append("The authenticated user lacks %Admin_Secure:U.")
        if not name.startswith("/") or name == "/":
            blockers.append("Application name must be an absolute path below root.")
        if any(item.get("Name") == name for item in apps):
            blockers.append("A web application with this name already exists.")
        if namespace not in namespaces:
            blockers.append("The selected namespace was not observed on this server.")
        if not dispatch_class.strip():
            blockers.append("A REST dispatch class is required.")
        if resource and resource not in {item.get("Name") for item in resources}:
            blockers.append(
                "The selected access resource was not observed on this server."
            )
        payload = {
            "NameSpace": namespace,
            "DispatchClass": dispatch_class,
            "Resource": resource,
            "Enabled": True,
            "Type": 2,
            "AutheEnabled": 32,
            "UseCookies": "Never",
            "SessionScope": "Strict",
            "Description": "Created through Armada Battery",
        }
        snapshot = {
            "secure_privilege": info.get("privileges", {}).get("Secure"),
            "apps": apps,
            "namespaces": sorted(namespaces),
            "resources": resources,
        }
        return self._finish_admin_plan(intent, rule, blockers, payload, snapshot)

    @serialized
    def prepare_grant_role(
        self,
        *,
        username: str,
        role_name: str,
        requested_by: str,
        role_reviewed: bool,
    ) -> dict[str, Any]:
        now = self.now()
        intent = Intent(
            id=str(uuid.uuid4()),
            kind=IntentKind.CHANGE,
            target=f"user:{username}",
            desired_outcome=f"User {username} has role {role_name}.",
            constraints={"role_reviewed": role_reviewed},
            requested_by=requested_by,
            requested_at=now,
            expires_at=now + timedelta(minutes=5),
        )
        rule = self._admin_rule("access.grant-role")
        info = self.adapter.get_info()
        blockers: list[str] = []
        if not info.get("privileges", {}).get("Secure", {}).get("use", False):
            blockers.append("The authenticated user lacks %Admin_Secure:U.")
        try:
            user = self.adapter.get_user(username)
        except AdapterError as exc:
            blockers.append(f"The target user could not be established: {exc}")
            user = {"Roles": []}
        try:
            role = self.adapter.get_role(role_name)
        except AdapterError as exc:
            blockers.append(f"The target role could not be established: {exc}")
            role = {}
        roles = list(user.get("Roles") or [])
        if role_name in roles:
            return self._satisfied_plan(
                intent, rule, f"{username} already has {role_name}."
            )
        if not role_reviewed:
            blockers.append(
                "The role's resources and inherited roles have not been reviewed."
            )
        if role_name == "%All":
            blockers.append(
                "Battery does not automate assignment of the unrestricted %All role."
            )
        payload = {"Roles": sorted(set(roles + [role_name]))}
        snapshot = {
            "secure_privilege": info.get("privileges", {}).get("Secure"),
            "user": user,
            "role": role,
        }
        return self._finish_admin_plan(
            intent,
            rule,
            blockers,
            payload,
            snapshot,
            context={"role": role, "role_name": role_name},
        )

    @serialized
    def prepare_schedule_task(
        self,
        *,
        task_id: int,
        period: str,
        start_time: str,
        every: str,
        day: str,
        requested_by: str,
    ) -> dict[str, Any]:
        now = self.now()
        intent = Intent(
            id=str(uuid.uuid4()),
            kind=IntentKind.CHANGE,
            target=f"task:{task_id}",
            desired_outcome="The existing task has the requested schedule.",
            constraints={"period": period, "start_time": start_time},
            requested_by=requested_by,
            requested_at=now,
            expires_at=now + timedelta(minutes=5),
        )
        rule = self._admin_rule("task.schedule-existing")
        info = self.adapter.get_info()
        task = self.adapter.get_task(task_id)
        blockers: list[str] = []
        privileges = info.get("privileges", {})
        if not (
            privileges.get("Task", {}).get("use", False)
            or privileges.get("Operate", {}).get("use", False)
        ):
            blockers.append("The authenticated user lacks Task or Operate privilege.")
        allowed_periods = {"Daily", "Weekly", "Monthly", "On Demand"}
        if period not in allowed_periods:
            blockers.append(
                "The requested schedule period is not supported by this workflow."
            )
        if period != "On Demand" and not self._valid_time(start_time):
            blockers.append("Start time must use 24-hour HH:MM or HH:MM:SS form.")
        limits = {"Daily": 7, "Weekly": 5, "Monthly": 12}
        if period in limits and (
            not every.isdigit() or not 1 <= int(every) <= limits[period]
        ):
            blockers.append(
                f"{period} interval must be between 1 and {limits[period]}."
            )
        if period == "Weekly" and (not day.isdigit() or not set(day) <= set("1234567")):
            blockers.append(
                "Weekly days must use digits 1 through 7, where 1 is Sunday."
            )
        if period == "Monthly" and (not day.isdigit() or not 1 <= int(day) <= 31):
            blockers.append(
                "Monthly day must be between 1 and 31; 31 means the last day."
            )
        payload = {
            "TimePeriod": period,
            "TimePeriodEvery": "" if period == "On Demand" else every,
            "TimePeriodDay": day if period in {"Weekly", "Monthly"} else "",
            "DailyFrequency": "Once",
            "DailyFrequencyTime": "",
            "DailyIncrement": "",
            "DailyStartTime": "" if period == "On Demand" else start_time,
            "DailyEndTime": "",
        }
        comparable = {key: task.get(key, "") for key in payload}
        if comparable == payload:
            return self._satisfied_plan(
                intent, rule, "The task already has this schedule."
            )
        snapshot = {
            "task_privilege": privileges.get("Task"),
            "operate_privilege": privileges.get("Operate"),
            "task": task,
        }
        return self._finish_admin_plan(intent, rule, blockers, payload, snapshot)

    @serialized
    def execute_admin(
        self, token: str, idempotency_key: str, operator: str | None = None
    ) -> dict[str, Any]:
        scope = f"admin:{idempotency_key}"
        if scope in self.idempotency:
            return self._repeat(scope, token, operator)
        cert = self.admin_certificates.get(_digest(token))
        if not cert:
            raise ValueError("Unknown administrative preflight certificate")
        if operator is not None and cert["operator"] != operator:
            raise ValueError("Preflight belongs to another operator")
        if cert["used"]:
            raise ValueError("Preflight certificate has already been used")
        from datetime import datetime

        if self.now() > datetime.fromisoformat(cert["expires_at"]):
            raise ValueError("Preflight evidence has expired")
        if not self.allow_changes:
            raise ValueError("Changes are disabled")
        current = self._admin_snapshot(cert)
        if _digest(current) != cert["snapshot_digest"]:
            raise ValueError("Target state changed after preflight; prepare again")
        if self.now() > datetime.fromisoformat(cert["expires_at"]):
            raise ValueError("Preflight evidence expired during refresh")
        cert["used"] = True
        receipt = Receipt(
            id=str(uuid.uuid4()),
            intent_id=cert["intent_id"],
            action_id=cert["action_id"],
            target=cert["target"],
            operator=cert["operator"],
            idempotency_key=idempotency_key,
            started_at=self.now(),
            status=ReceiptStatus.OUTCOME_UNKNOWN,
            before_evidence=tuple(cert.get("evidence_ids", [])),
            certificate_digest=_digest(token),
            verification_deadline=self.now() + timedelta(minutes=5),
            explanation="Dispatch reserved durably before sending the request.",
        )
        self.receipts[receipt.id] = receipt
        self.idempotency[scope] = receipt.id
        self.ledger.append("action_attempted", to_data(receipt))
        try:
            self._apply_admin(cert["action_id"], cert["target"], cert["payload"])
            receipt.transport_result = "IRIS accepted the configuration request"
        except AmbiguousTransport:
            receipt.transport_result = "response unavailable"
        except AdapterError:
            receipt.transport_result = "IRIS request did not establish an outcome"
        return self.reconcile_admin(receipt)

    def reconcile_admin(self, receipt: Receipt) -> dict[str, Any]:
        cert = next(
            (
                c
                for c in self.admin_certificates.values()
                if c["intent_id"] == receipt.intent_id
            ),
            None,
        )
        if cert is None:
            receipt.status = ReceiptStatus.OUTCOME_UNKNOWN
            receipt.explanation = (
                "The durable plan is unavailable. Do not resend this attempt."
            )
        else:
            try:
                action, target = receipt.action_id, receipt.target
                if action == "web-app.create":
                    observed = self.adapter.get_web_app(target.split(":", 1)[1])
                elif action == "access.grant-role":
                    observed = self.adapter.get_user(target.split(":", 1)[1])
                else:
                    observed = self.adapter.get_task(int(target.split(":", 1)[1]))
                evidence = self._observe("configuration-readback", target, observed)
                receipt.after_evidence = (evidence["id"],)
                verified = all(
                    self._normalized_field(k, observed.get(k))
                    == self._normalized_field(k, v)
                    for k, v in cert["payload"].items()
                )
            except AdapterError:
                verified = False
            if verified:
                receipt.status = ReceiptStatus.VERIFIED_SUCCESS
                receipt.finished_at = self.now()
                receipt.explanation = "Fresh configuration readback matches the requested state. This does not prove functional service behavior."
            else:
                receipt.status = ReceiptStatus.OUTCOME_UNKNOWN
                receipt.explanation = "Readback does not establish the requested outcome. The change may have occurred; reconcile without resending."
        self.ledger.append("action_reconciled", to_data(receipt))
        return to_data(receipt)

    @staticmethod
    def _normalized_field(key, value):
        if key == "Roles" and isinstance(value, list):
            return sorted(value)
        if (
            key in {"DailyStartTime", "DailyEndTime"}
            and isinstance(value, str)
            and len(value) == 5
        ):
            return value + ":00"
        return value

    def _finish_admin_plan(
        self,
        intent: Intent,
        rule: RuleSpec,
        blockers: list[str],
        payload: dict[str, Any],
        snapshot: dict[str, Any],
        *,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if _ORDER[rule.validation] < _ORDER[rule.minimum_execution_validation]:
            blockers.append(
                f"Rule validation is {rule.validation.value}; execution requires "
                f"{rule.minimum_execution_validation.value}."
            )
        if not self.allow_changes:
            blockers.append("Live state changes are disabled by server configuration.")
        evidence = self._observe("preflight-snapshot", intent.target, snapshot)
        finding = Finding(
            id=str(uuid.uuid4()),
            rule_id=rule.id,
            rule_version=rule.version,
            target=intent.target,
            state=FindingState.BLOCKED if blockers else FindingState.SAFE,
            summary="Plan ready."
            if not blockers
            else "More evidence or authority is required.",
            consequence="The proposed change affects IRIS configuration.",
            evidence_ids=(evidence["id"],),
            missing_evidence=tuple(blockers),
            recommended_actions=("Execute and verify",)
            if not blockers
            else ("Resolve blockers",),
            evaluated_at=self.now(),
            inference="requested state compared with fresh target and capability observations",
        )
        self.ledger.append("intent_created", to_data(intent))
        self.ledger.append("finding_evaluated", to_data(finding))
        certificate = None
        if not blockers:
            token = secrets.token_urlsafe(24)
            action_id = rule.id
            cert = {
                "token": token,
                "intent_id": intent.id,
                "action_id": action_id,
                "target": intent.target,
                "operator": intent.requested_by,
                "issued_at": self.now().isoformat(),
                "expires_at": (self.now() + timedelta(seconds=60)).isoformat(),
                "snapshot_digest": _digest(snapshot),
                "payload": payload,
                "context": context or {},
                "used": False,
                "evidence_ids": [evidence["id"]],
            }
            self.admin_certificates[_digest(token)] = cert
            certificate = dict(cert)
            certificate.pop("snapshot_digest")
            self.ledger.append(
                "preflight_issued",
                {**cert, "token": "[REDACTED]", "certificate_digest": _digest(token)},
            )
        return {
            "plan_state": "PLAN_READY" if not blockers else "NEEDS_EVIDENCE",
            "intent": to_data(intent),
            "finding": to_data(finding),
            "rule": to_data(rule),
            "proposed_change": sanitize(payload),
            "context": sanitize(context or {}),
            "certificate": certificate,
        }

    def _satisfied_plan(
        self, intent: Intent, rule: RuleSpec, summary: str
    ) -> dict[str, Any]:
        finding = Finding(
            id=str(uuid.uuid4()),
            rule_id=rule.id,
            rule_version=rule.version,
            target=intent.target,
            state=FindingState.SAFE,
            summary=summary,
            consequence="No state change is required.",
            evidence_ids=(),
            missing_evidence=(),
            recommended_actions=("No action",),
            evaluated_at=self.now(),
            inference="fresh readback already satisfies the requested outcome",
        )
        self.ledger.append("intent_created", to_data(intent))
        self.ledger.append("finding_evaluated", to_data(finding))
        return {
            "plan_state": "SATISFIED",
            "intent": to_data(intent),
            "finding": to_data(finding),
            "rule": to_data(rule),
            "proposed_change": {},
            "context": {},
            "certificate": None,
        }

    def _admin_rule(self, action: str) -> RuleSpec:
        common = {
            "web-app.create": (
                "Create a bounded REST application only when its name is unused and dependencies exist.",
                ("Application name is unused.", "Namespace and access resource exist."),
                (
                    "A dispatch class may exist but implement unintended behavior.",
                    "Authentication flags may vary by IRIS version.",
                ),
            ),
            "access.grant-role": (
                "Add one reviewed existing role while preserving the user's existing direct roles.",
                (
                    "The selected identity and role are correct.",
                    "Inherited access has been reviewed.",
                ),
                (
                    "A role can inherit broader privileges than its name suggests.",
                    "External identity mapping may add other access.",
                ),
            ),
            "task.schedule-existing": (
                "Change only schedule fields on an existing task and verify them by readback.",
                (
                    "The task definition is already valid.",
                    "The requested local server time is intended.",
                ),
                (
                    "A valid schedule can overlap a long prior run.",
                    "Server timezone may differ from operator timezone.",
                ),
            ),
        }
        rationale, assumptions, counterexamples = common[action]
        minimum = (
            RuleValidation.SIMULATED
            if self.adapter.synthetic
            else RuleValidation.LIVE_OBSERVED
        )
        return RuleSpec(
            id=action,
            version=1,
            rationale=rationale,
            assumptions=assumptions,
            supported_versions=("synthetic-v1", "IRIS SysAdmin API v1"),
            contradictors=(
                "Required privilege is absent.",
                "Target state changed after preflight.",
            ),
            counterexamples=counterexamples,
            synthetic_tests=(
                f"{action}.positive",
                f"{action}.blocked",
                f"{action}.already-satisfied",
            ),
            live_validations=(),
            validation=self.rule.validation,
            minimum_execution_validation=minimum,
        )

    def _admin_snapshot(self, cert: dict[str, Any]) -> dict[str, Any]:
        action = cert["action_id"]
        target = cert["target"]
        info = self.adapter.get_info()
        if action == "web-app.create":
            return {
                "secure_privilege": info.get("privileges", {}).get("Secure"),
                "apps": self.adapter.list_web_apps(),
                "namespaces": sorted(
                    item.get("name")
                    for item in info.get("namespaces", [])
                    if item.get("name")
                ),
                "resources": self.adapter.list_resources(),
            }
        if action == "access.grant-role":
            username = target.split(":", 1)[1]
            role_name = cert["context"]["role_name"]
            return {
                "secure_privilege": info.get("privileges", {}).get("Secure"),
                "user": self.adapter.get_user(username),
                "role": self.adapter.get_role(role_name),
            }
        if action == "task.schedule-existing":
            privileges = info.get("privileges", {})
            return {
                "task_privilege": privileges.get("Task"),
                "operate_privilege": privileges.get("Operate"),
                "task": self.adapter.get_task(int(target.split(":", 1)[1])),
            }
        raise ValueError(f"Unsupported action {action}")

    def _apply_admin(self, action: str, target: str, payload: dict[str, Any]) -> None:
        if action == "web-app.create":
            self.adapter.put_web_app(target.split(":", 1)[1], payload)
        elif action == "access.grant-role":
            self.adapter.put_user(target.split(":", 1)[1], payload)
        elif action == "task.schedule-existing":
            self.adapter.put_task(int(target.split(":", 1)[1]), payload)
        else:
            raise ValueError(f"Unsupported action {action}")

    def _verify_admin(self, action: str, target: str, payload: dict[str, Any]) -> bool:
        if action == "web-app.create":
            observed = self.adapter.get_web_app(target.split(":", 1)[1])
        elif action == "access.grant-role":
            observed = self.adapter.get_user(target.split(":", 1)[1])
        elif action == "task.schedule-existing":
            observed = self.adapter.get_task(int(target.split(":", 1)[1]))
        else:
            return False
        return all(observed.get(key) == value for key, value in payload.items())

    @staticmethod
    def _valid_time(value: str) -> bool:
        parts = value.split(":")
        if len(parts) not in {2, 3} or not all(part.isdigit() for part in parts):
            return False
        hour, minute = int(parts[0]), int(parts[1])
        second = int(parts[2]) if len(parts) == 3 else 0
        return hour < 24 and minute < 60 and second < 60
