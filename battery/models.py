"""Public domain types for the first Armada Battery vertical slice."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class Quality(str, Enum):
    VALID = "VALID"
    STALE = "STALE"
    MALFORMED = "MALFORMED"
    FORBIDDEN = "FORBIDDEN"
    UNSUPPORTED = "UNSUPPORTED"
    CONFLICTED = "CONFLICTED"


class IntentKind(str, Enum):
    INSPECT = "INSPECT"
    CREATE = "CREATE"
    CHANGE = "CHANGE"
    RUN = "RUN"
    SUSPEND = "SUSPEND"
    RESUME = "RESUME"
    DELETE = "DELETE"


class FindingState(str, Enum):
    SAFE = "SAFE"
    WATCH = "WATCH"
    ACT = "ACT"
    BLOCKED = "BLOCKED"
    VERIFY = "VERIFY"


class RuleValidation(str, Enum):
    DRAFT = "DRAFT"
    SIMULATED = "SIMULATED"
    LIVE_OBSERVED = "LIVE_OBSERVED"
    APPROVED = "APPROVED"


class ReceiptStatus(str, Enum):
    VERIFIED_SUCCESS = "VERIFIED_SUCCESS"
    VERIFIED_FAILURE = "VERIFIED_FAILURE"
    EXECUTED_UNVERIFIED = "EXECUTED_UNVERIFIED"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"
    BLOCKED_BEFORE_EXECUTION = "BLOCKED_BEFORE_EXECUTION"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class Intent:
    id: str
    kind: IntentKind
    target: str
    desired_outcome: str
    constraints: dict[str, Any]
    requested_by: str
    requested_at: datetime
    expires_at: datetime | None = None


@dataclass(frozen=True)
class Observation:
    id: str
    source: str
    target: str
    captured_at: datetime
    expires_at: datetime | None
    value: Any
    quality: Quality = Quality.VALID
    complete: bool = True


@dataclass(frozen=True)
class RuleSpec:
    id: str
    version: int
    rationale: str
    assumptions: tuple[str, ...]
    supported_versions: tuple[str, ...]
    contradictors: tuple[str, ...]
    counterexamples: tuple[str, ...]
    synthetic_tests: tuple[str, ...]
    live_validations: tuple[str, ...]
    validation: RuleValidation
    minimum_execution_validation: RuleValidation


@dataclass(frozen=True)
class Finding:
    id: str
    rule_id: str
    rule_version: int
    target: str
    state: FindingState
    summary: str
    consequence: str
    evidence_ids: tuple[str, ...]
    missing_evidence: tuple[str, ...]
    recommended_actions: tuple[str, ...]
    evaluated_at: datetime
    inference: str


@dataclass
class PreflightCertificate:
    token: str
    intent_id: str
    action_id: str
    target: str
    operator: str
    issued_at: datetime
    expires_at: datetime
    evidence_digest: str
    history_fingerprints: tuple[str, ...]
    used: bool = False
    evidence_ids: tuple[str, ...] = ()


@dataclass
class Receipt:
    id: str
    intent_id: str
    action_id: str
    target: str
    operator: str
    idempotency_key: str
    started_at: datetime
    status: ReceiptStatus
    transport_result: str = "not sent"
    finished_at: datetime | None = None
    before_evidence: tuple[str, ...] = field(default_factory=tuple)
    after_evidence: tuple[str, ...] = field(default_factory=tuple)
    explanation: str = ""
    certificate_digest: str = ""
    history_before: tuple[str, ...] = field(default_factory=tuple)
    verification_deadline: datetime | None = None


def to_data(value: Any) -> Any:
    """Convert domain objects into stable JSON-compatible data."""
    if hasattr(value, "__dataclass_fields__"):
        return to_data(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): to_data(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_data(item) for item in value]
    return value
