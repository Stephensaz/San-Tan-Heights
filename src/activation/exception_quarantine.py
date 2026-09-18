from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Iterable

import yaml


ALLOWED_REPAIR_STATES = {
    "OPEN",
    "QUARANTINED",
    "REPAIR_PENDING",
    "REPAIRED_PENDING_REPLAY",
    "REPLAY_VALIDATED",
    "CLOSED",
}

ALLOWED_SEVERITIES = {"INFO", "WARNING", "MATERIAL", "CRITICAL"}
ALLOWED_SCOPE_TYPES = {"PROPERTY", "FIELD", "ARTIFACT", "FINDING", "REPORT"}


@dataclass(frozen=True)
class ExceptionDecision:
    exception_id: str
    exception_class: str
    owning_layer: str
    severity: str
    repair_state: str
    is_defect: bool
    quarantine_required: bool
    publication_allowed: bool
    substitution_allowed: bool
    fingerprint: str


@dataclass(frozen=True)
class ExceptionLedgerAudit:
    records: int
    defects: int
    quarantined: int
    non_defect_conditions: int
    publication_allowed: int
    substitution_allowed: int
    known_partial_present: bool
    aggregate_fingerprint: str


@dataclass(frozen=True)
class RepairReplayAudit:
    repaired_exception_id: str
    changed_dependency_keys: tuple[str, ...]
    unchanged_dependency_keys: tuple[str, ...]
    unauthorized_changes: tuple[str, ...]


def _canonical_hash(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return sha256(encoded).hexdigest()


def load_exception_policy(path: str | Path) -> dict:
    policy = yaml.safe_load(Path(path).read_text())
    if policy.get("exception_policy_id") != "STH-M9-008-EXCEPTION-QUARANTINE-v1.0":
        raise ValueError("unexpected M9-008 exception policy id")
    if str(policy.get("version")) != "1.0.0" or policy.get("status") != "FROZEN":
        raise ValueError("M9-008 exception policy must be FROZEN v1.0.0")
    return policy


def evaluate_exception(record: dict, policy: dict) -> ExceptionDecision:
    required = {
        "exception_id",
        "canonical_property_id",
        "scope_type",
        "scope_key",
        "exception_class",
        "reason_code",
        "severity",
        "repair_state",
        "owning_layer",
    }
    missing = sorted(required - set(record))
    if missing:
        raise ValueError(f"exception record missing required fields: {', '.join(missing)}")

    if record["scope_type"] not in ALLOWED_SCOPE_TYPES:
        raise ValueError("unsupported exception scope type")
    if record["severity"] not in ALLOWED_SEVERITIES:
        raise ValueError("unsupported exception severity")
    if record["repair_state"] not in ALLOWED_REPAIR_STATES:
        raise ValueError("unsupported repair state")

    classes = policy["exception_classes"]
    if record["exception_class"] not in classes:
        raise ValueError(f"unknown exception class {record['exception_class']}")
    class_policy = classes[record["exception_class"]]

    if record["owning_layer"] != class_policy["owning_layer"]:
        raise ValueError("exception owning layer mismatch")

    is_defect = bool(class_policy["is_defect"])
    quarantine_required = bool(class_policy["quarantine_required"])

    if record["exception_class"] in policy["non_defect_condition_classes"]:
        is_defect = False

    publication_allowed = bool(class_policy["publication_allowed"])
    waiver_requested = bool(record.get("waiver_requested", False))
    if waiver_requested and not publication_allowed:
        publication_allowed = False

    if record["repair_state"] in {"QUARANTINED", "REPAIR_PENDING", "REPAIRED_PENDING_REPLAY"}:
        publication_allowed = False

    substitution_allowed = False

    fingerprint_payload = {
        "exception_id": record["exception_id"],
        "canonical_property_id": record["canonical_property_id"],
        "scope_type": record["scope_type"],
        "scope_key": record["scope_key"],
        "exception_class": record["exception_class"],
        "reason_code": record["reason_code"],
        "severity": record["severity"],
        "repair_state": record["repair_state"],
        "owning_layer": record["owning_layer"],
        "source_fingerprint": record.get("source_fingerprint"),
        "supersedes_exception_id": record.get("supersedes_exception_id"),
        "is_defect": is_defect,
        "quarantine_required": quarantine_required,
        "publication_allowed": publication_allowed,
        "substitution_allowed": substitution_allowed,
    }

    return ExceptionDecision(
        exception_id=record["exception_id"],
        exception_class=record["exception_class"],
        owning_layer=record["owning_layer"],
        severity=record["severity"],
        repair_state=record["repair_state"],
        is_defect=is_defect,
        quarantine_required=quarantine_required,
        publication_allowed=publication_allowed,
        substitution_allowed=substitution_allowed,
        fingerprint=_canonical_hash(fingerprint_payload),
    )


def audit_exception_ledger(records: Iterable[dict], policy: dict) -> ExceptionLedgerAudit:
    records = list(records)
    seen_ids: set[str] = set()
    decisions: list[ExceptionDecision] = []
    known_partial = policy["known_governed_exception"]
    known_partial_present = False

    for record in records:
        exception_id = record.get("exception_id")
        if exception_id in seen_ids:
            raise ValueError("duplicate exception_id")
        seen_ids.add(exception_id)
        decision = evaluate_exception(record, policy)
        decisions.append(decision)

        if (
            record["canonical_property_id"] == known_partial["canonical_property_id"]
            and record["scope_key"] == known_partial["scope_key"]
            and record["exception_class"] == known_partial["exception_class"]
        ):
            known_partial_present = True
            if record["repair_state"] == "CLOSED" and not record.get("repair_evidence_fingerprint"):
                raise ValueError("known governed exception cannot close without repair evidence")

    if not known_partial_present:
        raise ValueError("known governed frontage exception missing from ledger")

    aggregate = sha256(("\n".join(sorted(d.fingerprint for d in decisions)) + "\n").encode("utf-8")).hexdigest()
    return ExceptionLedgerAudit(
        records=len(decisions),
        defects=sum(1 for d in decisions if d.is_defect),
        quarantined=sum(1 for d in decisions if d.quarantine_required),
        non_defect_conditions=sum(1 for d in decisions if not d.is_defect),
        publication_allowed=sum(1 for d in decisions if d.publication_allowed),
        substitution_allowed=sum(1 for d in decisions if d.substitution_allowed),
        known_partial_present=known_partial_present,
        aggregate_fingerprint=aggregate,
    )


def validate_exception_accounting(previous_records: Iterable[dict], current_records: Iterable[dict]) -> None:
    previous = {r["exception_id"]: r for r in previous_records}
    current = {r["exception_id"]: r for r in current_records}
    missing = sorted(set(previous) - set(current))
    for exception_id in missing:
        prior = previous[exception_id]
        replacement = [r for r in current.values() if r.get("supersedes_exception_id") == exception_id]
        if not replacement:
            raise ValueError(f"exception silently disappeared: {exception_id}")


def validate_repair_replay(
    repaired_exception_id: str,
    allowed_dependency_keys: Iterable[str],
    before_fingerprints: dict[str, str],
    after_fingerprints: dict[str, str],
) -> RepairReplayAudit:
    allowed = set(allowed_dependency_keys)
    if set(before_fingerprints) != set(after_fingerprints):
        raise ValueError("repair replay dependency key set drift")

    changed = tuple(sorted(k for k in before_fingerprints if before_fingerprints[k] != after_fingerprints[k]))
    unauthorized = tuple(sorted(k for k in changed if k not in allowed))
    unchanged = tuple(sorted(k for k in before_fingerprints if k not in changed))

    if unauthorized:
        raise ValueError(f"repair replay changed unaffected dependencies: {', '.join(unauthorized)}")
    if not changed:
        raise ValueError("repair replay produced no governed dependency change")

    return RepairReplayAudit(
        repaired_exception_id=repaired_exception_id,
        changed_dependency_keys=changed,
        unchanged_dependency_keys=unchanged,
        unauthorized_changes=unauthorized,
    )
