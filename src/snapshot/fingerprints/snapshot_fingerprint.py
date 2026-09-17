from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID
from src.shared.hash import sha256_canonical
from src.snapshot.findings.freezer import FrozenFinding
from src.snapshot.governed_state.models import GovernedDependency

_VARIANTS = ("AGENT", "SELLER", "PUBLIC")
_SCOPE_VARIANTS = {
    "AGENT": frozenset({"AGENT"}),
    "SELLER": frozenset({"SELLER"}),
    "PUBLIC": frozenset({"PUBLIC"}),
    "AGENT_SELLER": frozenset({"AGENT", "SELLER"}),
    "ALL": frozenset({"AGENT", "SELLER", "PUBLIC"}),
    "NONE": frozenset(),
}


@dataclass(frozen=True)
class SnapshotFingerprints:
    semantic_fingerprint: str
    agent_semantic_fingerprint: str
    seller_semantic_fingerprint: str
    public_semantic_fingerprint: str


class SnapshotFingerprintEngine:
    def _finding_entry(self, f: FrozenFinding) -> dict:
        return {"finding_id": f.finding_id, "semantic_fingerprint": f.semantic_fingerprint}

    def _dependency_entry(self, d: GovernedDependency) -> dict:
        return {
            "dependency_type": d.dependency_type,
            "dependency_id": d.dependency_id,
            "semantic_fingerprint": d.semantic_fingerprint,
        }

    def _base(self, property_id: UUID, intelligence_schema_version: str, governance_schema_version: str) -> dict:
        return {
            "property_id": str(property_id),
            "intelligence_schema_version": intelligence_schema_version,
            "governance_schema_version": governance_schema_version,
        }

    @staticmethod
    def _sorted_findings(findings: list[dict]) -> list[dict]:
        return sorted(findings, key=lambda x: (x["finding_id"], x["semantic_fingerprint"]))

    @staticmethod
    def _sorted_dependencies(dependencies: list[dict]) -> list[dict]:
        return sorted(dependencies, key=lambda x: (x["dependency_type"], x["dependency_id"], x["semantic_fingerprint"]))

    def calculate(
        self,
        *,
        property_id: UUID,
        intelligence_schema_version: str,
        governance_schema_version: str,
        findings: tuple[FrozenFinding, ...],
        dependencies: tuple[GovernedDependency, ...],
    ) -> SnapshotFingerprints:
        base = self._base(property_id, intelligence_schema_version, governance_schema_version)
        overall = {
            **base,
            "findings": self._sorted_findings([self._finding_entry(f) for f in findings]),
            "dependencies": self._sorted_dependencies([self._dependency_entry(d) for d in dependencies]),
        }
        overall_fp = sha256_canonical(overall)

        variant_fps: dict[str, str] = {}
        for variant in _VARIANTS:
            vf = [
                self._finding_entry(f)
                for f in findings
                if variant in _SCOPE_VARIANTS.get(f.publication_scope, frozenset())
            ]
            vd = [self._dependency_entry(d) for d in dependencies if variant in d.variant_scope]
            projection = {
                **base,
                "variant": variant,
                "findings": self._sorted_findings(vf),
                "dependencies": self._sorted_dependencies(vd),
            }
            variant_fps[variant] = sha256_canonical(projection)
        return SnapshotFingerprints(
            semantic_fingerprint=overall_fp,
            agent_semantic_fingerprint=variant_fps["AGENT"],
            seller_semantic_fingerprint=variant_fps["SELLER"],
            public_semantic_fingerprint=variant_fps["PUBLIC"],
        )
