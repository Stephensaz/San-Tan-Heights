from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

import yaml

from src.presentation.package import PresentationAudience

_EVIDENCE_RANK = {"LIGHT": 1, "STANDARD": 2, "DETAILED": 3}
_CONFIDENCE_RANK = {"SELECTIVE": 1, "FRIENDLY": 2, "DETAILED": 3}
_FILE_BY_AUDIENCE = {
    PresentationAudience.AGENT: "agent.yaml",
    PresentationAudience.SELLER: "seller.yaml",
    PresentationAudience.PUBLIC: "public.yaml",
}


@dataclass(frozen=True)
class AudiencePresentationPolicy:
    audience: PresentationAudience
    policy_id: str
    version: str
    allowed_classifications: frozenset[str]
    allowed_publication_scopes: frozenset[str]
    evidence_depth: str
    confidence_visibility: str
    required_sections: tuple[str, ...]
    optional_sections: tuple[str, ...]

    def allows(self, *, classification: str, publication_scope: str) -> bool:
        return classification in self.allowed_classifications and publication_scope in self.allowed_publication_scopes

    def require_allowed(self, *, classification: str, publication_scope: str) -> None:
        if not self.allows(classification=classification, publication_scope=publication_scope):
            raise ValueError(
                f"content is not eligible for {self.audience.value}: "
                f"classification={classification}, publication_scope={publication_scope}"
            )


@dataclass(frozen=True)
class AudiencePresentationPolicies:
    policies: Mapping[PresentationAudience, AudiencePresentationPolicy]

    @classmethod
    def from_repository(cls, root: str | Path) -> "AudiencePresentationPolicies":
        root = Path(root)
        loaded: dict[PresentationAudience, AudiencePresentationPolicy] = {}
        for audience, filename in _FILE_BY_AUDIENCE.items():
            raw = yaml.safe_load((root / "registries" / "report-variants" / filename).read_text())
            if raw.get("variant") != audience.value:
                raise ValueError(f"variant mismatch for {audience.value}")
            evidence_depth = str(raw.get("evidence_depth"))
            confidence_visibility = str(raw.get("confidence_visibility"))
            if evidence_depth not in _EVIDENCE_RANK:
                raise ValueError(f"unsupported evidence depth: {evidence_depth}")
            if confidence_visibility not in _CONFIDENCE_RANK:
                raise ValueError(f"unsupported confidence visibility: {confidence_visibility}")
            loaded[audience] = AudiencePresentationPolicy(
                audience=audience,
                policy_id=str(raw["policy_id"]),
                version=str(raw["version"]),
                allowed_classifications=frozenset(str(v) for v in raw.get("allowed_classifications") or ()),
                allowed_publication_scopes=frozenset(str(v) for v in raw.get("allowed_publication_scopes") or ()),
                evidence_depth=evidence_depth,
                confidence_visibility=confidence_visibility,
                required_sections=tuple(str(v) for v in raw.get("required_sections") or ()),
                optional_sections=tuple(str(v) for v in raw.get("optional_sections") or ()),
            )

        agent = loaded[PresentationAudience.AGENT]
        seller = loaded[PresentationAudience.SELLER]
        public = loaded[PresentationAudience.PUBLIC]
        if not (_EVIDENCE_RANK[agent.evidence_depth] >= _EVIDENCE_RANK[seller.evidence_depth] >= _EVIDENCE_RANK[public.evidence_depth]):
            raise ValueError("evidence depth must decrease Agent -> Seller -> Public")
        if not (_CONFIDENCE_RANK[agent.confidence_visibility] >= _CONFIDENCE_RANK[seller.confidence_visibility] >= _CONFIDENCE_RANK[public.confidence_visibility]):
            raise ValueError("confidence visibility must decrease Agent -> Seller -> Public")
        if not (public.allowed_classifications <= seller.allowed_classifications <= agent.allowed_classifications):
            raise ValueError("classification access must narrow Agent -> Seller -> Public")

        return cls(MappingProxyType(loaded))

    def for_audience(self, audience: PresentationAudience) -> AudiencePresentationPolicy:
        return self.policies[audience]
