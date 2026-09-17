from __future__ import annotations
from dataclasses import asdict
from src.shared.hash import sha256_canonical
from src.snapshot.findings.freezer import FrozenFinding
from src.snapshot.passports.passport_reference import PassportReference


class FindingFingerprintMismatch(ValueError):
    pass


class FindingFingerprintEngine:
    """Calculates a semantic fingerprint from governed finding content only."""

    def semantic_projection(self, finding: FrozenFinding, passport: PassportReference) -> dict:
        if passport.finding_id != finding.finding_id:
            raise ValueError("Passport reference does not belong to finding")
        return {
            "finding_type": finding.finding_type,
            "canonical_value": finding.canonical_value,
            "confidence_code": finding.confidence_code,
            "qa_status": finding.qa_status,
            "production_status": finding.production_status,
            "publication_scope": finding.publication_scope,
            "approved_wording": {
                "agent": finding.agent_wording,
                "seller": finding.seller_wording,
                "public": finding.public_wording,
            },
            "wording_versions": {
                "agent": finding.agent_wording_version,
                "seller": finding.seller_wording_version,
                "public": finding.public_wording_version,
            },
            "evidence_reference_set_hash": finding.evidence_reference_set_hash,
            "passport_semantic_fingerprint": passport.passport_semantic_fingerprint,
        }

    def calculate(self, finding: FrozenFinding, passport: PassportReference) -> str:
        return sha256_canonical(self.semantic_projection(finding, passport))

    def verify_upstream(self, finding: FrozenFinding, passport: PassportReference) -> str:
        calculated = self.calculate(finding, passport)
        if calculated != finding.semantic_fingerprint:
            raise FindingFingerprintMismatch(
                f"UPSTREAM_FINDING_FINGERPRINT_MISMATCH: {finding.finding_id}"
            )
        return calculated
