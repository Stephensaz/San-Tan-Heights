from __future__ import annotations
from collections.abc import Callable
from .passport_reference import PassportReference
from src.snapshot.findings.freezer import FrozenFinding


class PassportLineageError(ValueError):
    pass


class PassportLineageCapture:
    """Captures immutable Passport references for frozen findings.

    `resolver(passport_id, passport_version)` must return a PassportReference-like
    object for the exact immutable Passport version requested. The snapshot layer
    never falls forward to a newer Passport version.
    """

    def __init__(self, resolver: Callable[[str, str], PassportReference]):
        self._resolver = resolver

    def capture(self, findings: tuple[FrozenFinding, ...]) -> tuple[PassportReference, ...]:
        refs: list[PassportReference] = []
        seen_findings: set[str] = set()
        for finding in findings:
            if finding.finding_id in seen_findings:
                raise PassportLineageError(f"duplicate finding lineage: {finding.finding_id}")
            seen_findings.add(finding.finding_id)
            try:
                ref = self._resolver(finding.passport_id, finding.passport_version)
                ref.validate()
            except Exception as exc:
                raise PassportLineageError(
                    f"unable to resolve immutable Passport {finding.passport_id}@{finding.passport_version}"
                ) from exc
            if ref.passport_id != finding.passport_id or ref.passport_version != finding.passport_version:
                raise PassportLineageError(f"Passport identity/version mismatch for {finding.finding_id}")
            if ref.finding_id != finding.finding_id:
                raise PassportLineageError(f"Passport finding mismatch for {finding.finding_id}")
            if ref.evidence_reference_set_hash != finding.evidence_reference_set_hash:
                raise PassportLineageError(f"evidence reference set mismatch for {finding.finding_id}")
            if ref.passport_qa_status != "PASS":
                raise PassportLineageError(f"Passport QA must be PASS for production finding {finding.finding_id}")
            refs.append(ref)
        return tuple(sorted(refs, key=lambda r: (r.finding_id, r.passport_id, r.passport_version)))
