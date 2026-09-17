from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from typing import Mapping, Any
from uuid import UUID, uuid4
from src.shared.canonical_json import canonical_json
from .sample import ManualAuditPolicy, ManualAuditSample

@dataclass(frozen=True)
class ManualAuditEvidence:
    manual_audit_evidence_id: UUID
    manual_audit_sample_id: UUID
    property_id: UUID
    audit_status: str
    checklist_version: str
    checklist_results: Mapping[str, Any]
    notes: str | None
    evidence_hash: str
    reviewed_by: str

class ManualAuditEvidenceCapture:
    def capture(self, *, policy: ManualAuditPolicy, sample: ManualAuditSample, property_id: UUID,
                audit_status: str, checklist_results: Mapping[str, Any], reviewed_by: str,
                notes: str | None=None, manual_audit_evidence_id: UUID | None=None) -> ManualAuditEvidence:
        if property_id not in set(sample.sampled_property_ids):
            raise ValueError('property is not part of manual audit sample')
        if audit_status not in set(policy.allowed_audit_statuses):
            raise ValueError('invalid manual audit status')
        if not reviewed_by.strip(): raise ValueError('reviewed_by is required')
        results=dict(checklist_results)
        if not results: raise ValueError('checklist_results are required')
        payload={'manual_audit_sample_id':str(sample.manual_audit_sample_id),'property_id':str(property_id),
                 'audit_status':audit_status,'checklist_version':policy.checklist_version,
                 'checklist_results':results,'notes':notes}
        fp=sha256(canonical_json(payload).encode('utf-8')).hexdigest()
        return ManualAuditEvidence(manual_audit_evidence_id or uuid4(),sample.manual_audit_sample_id,property_id,
            audit_status,policy.checklist_version,results,notes,fp,reviewed_by)
