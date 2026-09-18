from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Iterable, Mapping

import yaml

from .controlled_publication import PublicationBatchResult, PublicationPointer, apply_pointer_batch, rollback_pointer_batch


@dataclass(frozen=True)
class ReplayRecord:
    canonical_property_id: str
    output_tier: str
    before_fingerprint: str
    after_fingerprint: str
    impacted: bool
    failure_code: str | None = None


@dataclass(frozen=True)
class ReplayAudit:
    records: int
    impacted_records: int
    unchanged_records: int
    changed_impacted_records: int
    changed_unimpacted_records: int
    failed_records: int
    isolated_failures: int
    rollback_verified: bool
    replay_fingerprint: str


def _canonical_hash(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return sha256(encoded).hexdigest()


def load_replay_policy(path: str | Path) -> dict:
    policy = yaml.safe_load(Path(path).read_text())
    if policy.get("replay_policy_id") != "STH-M9-011-REFRESH-REGEN-ROLLBACK-v1.0":
        raise ValueError("unexpected M9-011 replay policy id")
    if str(policy.get("version")) != "1.0.0" or policy.get("status") != "FROZEN":
        raise ValueError("M9-011 replay policy must be FROZEN v1.0.0")
    return policy


def audit_replay(records: Iterable[ReplayRecord], policy: Mapping[str, object]) -> ReplayAudit:
    rows = tuple(records)
    if not rows:
        raise ValueError("replay requires records")

    seen: set[tuple[str, str]] = set()
    changed_impacted = 0
    changed_unimpacted = 0
    failed = 0
    isolated_failures = 0

    for row in rows:
        key = (row.canonical_property_id, row.output_tier)
        if key in seen:
            raise ValueError("duplicate replay record")
        seen.add(key)

        if not row.canonical_property_id.startswith("STH-"):
            raise ValueError("invalid canonical property id")
        if row.output_tier not in {"AGENT", "SELLER", "PUBLIC"}:
            raise ValueError("invalid report tier")
        for value in (row.before_fingerprint, row.after_fingerprint):
            if len(value) != 64:
                raise ValueError("replay fingerprints must be sha256")

        changed = row.before_fingerprint != row.after_fingerprint
        if changed and row.impacted:
            changed_impacted += 1
        if changed and not row.impacted:
            changed_unimpacted += 1

        if row.failure_code:
            failed += 1
            if row.impacted:
                isolated_failures += 1
            else:
                raise ValueError("failure occurred outside impacted dependency scope")

    if changed_unimpacted:
        raise ValueError("unchanged dependency scope fingerprint drift")
    if bool(policy["governance"]["unchanged_fingerprint_stability_required"]) and changed_unimpacted:
        raise ValueError("unchanged fingerprint stability violated")

    payload = {
        "records": [
            {
                "canonical_property_id": r.canonical_property_id,
                "output_tier": r.output_tier,
                "before_fingerprint": r.before_fingerprint,
                "after_fingerprint": r.after_fingerprint,
                "impacted": r.impacted,
                "failure_code": r.failure_code,
            }
            for r in sorted(rows, key=lambda x: (x.canonical_property_id, x.output_tier))
        ],
        "changed_impacted_records": changed_impacted,
        "changed_unimpacted_records": changed_unimpacted,
        "failed_records": failed,
    }

    return ReplayAudit(
        records=len(rows),
        impacted_records=sum(1 for r in rows if r.impacted),
        unchanged_records=sum(1 for r in rows if not r.impacted),
        changed_impacted_records=changed_impacted,
        changed_unimpacted_records=changed_unimpacted,
        failed_records=failed,
        isolated_failures=isolated_failures,
        rollback_verified=False,
        replay_fingerprint=_canonical_hash(payload),
    )


def verify_publication_rollback(
    *,
    before: Iterable[PublicationPointer],
    batch: PublicationBatchResult,
) -> bool:
    before_tuple = tuple(before)
    after = apply_pointer_batch(batch=batch, current_pointers=before_tuple)
    restored = rollback_pointer_batch(before=before_tuple, after=after, batch=batch)
    before_sorted = tuple(sorted(before_tuple, key=lambda p: (p.canonical_property_id, p.output_tier)))
    return restored == before_sorted


def validate_replay_failure_isolation(records: Iterable[ReplayRecord]) -> None:
    rows = tuple(records)
    failed_properties = {r.canonical_property_id for r in rows if r.failure_code}
    for row in rows:
        if row.canonical_property_id not in failed_properties and row.failure_code:
            raise ValueError("unexpected replay failure")
    # A failed impacted property may not force unrelated properties to change.
    for row in rows:
        if row.canonical_property_id not in failed_properties and not row.impacted:
            if row.before_fingerprint != row.after_fingerprint:
                raise ValueError("failure leaked into unaffected property")


def validate_m9_011_repository_binding(root: str | Path = ".") -> str:
    root = Path(root)
    m9_010 = json.loads((root / "certification-evidence/m9-010/controlled-publication-v1.0.json").read_text())
    m9_009 = json.loads((root / "certification-evidence/m9-009/full-corpus-qa-v1.0.json").read_text())
    replay_policy = load_replay_policy(root / "registries/activation/m9-011-refresh-replay-v1.0.yaml")

    required_docs = (
        "docs/implementation/M2-019.md",
        "docs/implementation/M3-026.md",
        "docs/implementation/M7-023.md",
    )
    for rel in required_docs:
        if "Status: ACCEPTED" not in (root / rel).read_text():
            raise ValueError(f"upstream replay control not accepted: {rel}")

    if m9_010.get("status") != "ACCEPTED":
        raise ValueError("M9-010 must be accepted before M9-011")
    if m9_009.get("status") != "ACCEPTED":
        raise ValueError("M9-009 must remain accepted")
    if m9_010.get("waivers") != 0 or m9_009["defects"].get("waivers") != 0:
        raise ValueError("waivers are prohibited")

    payload = {
        "m9_010_binding_fingerprint": m9_010["binding_fingerprint"],
        "m9_009_qa_fingerprint": m9_009["qa_fingerprint"],
        "replay_policy_version": replay_policy["version"],
        "dependency_impact_control": "M2-019",
        "regeneration_control": "M3-026",
        "rollback_control": "M7-023",
    }
    return _canonical_hash(payload)
