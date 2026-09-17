from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import re
from typing import Iterable

from src.presentation.audience.policy import AudiencePresentationPolicy
from src.presentation.package import PresentationAudience
from src.shared.canonical_json import canonical_json

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ChangeType(str, Enum):
    NEW_FINDING = "NEW_FINDING"
    FINDING_RETIRED = "FINDING_RETIRED"
    VALUE_CHANGED = "VALUE_CHANGED"
    STATE_CHANGED = "STATE_CHANGED"
    CONFIDENCE_CHANGED = "CONFIDENCE_CHANGED"
    FRESHNESS_CHANGED = "FRESHNESS_CHANGED"
    EVIDENCE_CHANGED = "EVIDENCE_CHANGED"
    LIMITATION_CHANGED = "LIMITATION_CHANGED"
    CORRECTION = "CORRECTION"
    CONFLICT_RESOLVED = "CONFLICT_RESOLVED"
    DIAGRAM_CHANGED = "DIAGRAM_CHANGED"
    MEDIA_CHANGED = "MEDIA_CHANGED"
    MARKET_CONTEXT_CHANGED = "MARKET_CONTEXT_CHANGED"
    WORDING_ONLY = "WORDING_ONLY"
    NO_SEMANTIC_CHANGE = "NO_SEMANTIC_CHANGE"


class ChangeMateriality(str, Enum):
    MATERIAL = "MATERIAL"
    DETAIL = "DETAIL"


class ChangeGroupKey(str, Enum):
    NEWLY_VERIFIED = "NEWLY_VERIFIED"
    UPDATED = "UPDATED"
    CORRECTED = "CORRECTED"
    EVIDENCE_UPDATED = "EVIDENCE_UPDATED"
    MARKET_CONTEXT_UPDATED = "MARKET_CONTEXT_UPDATED"


_GROUP_TITLES = {
    ChangeGroupKey.NEWLY_VERIFIED: "Newly Verified",
    ChangeGroupKey.UPDATED: "Updated",
    ChangeGroupKey.CORRECTED: "Corrected",
    ChangeGroupKey.EVIDENCE_UPDATED: "Evidence Updated",
    ChangeGroupKey.MARKET_CONTEXT_UPDATED: "Market Context Updated",
}

_GROUP_ORDER = (
    ChangeGroupKey.NEWLY_VERIFIED,
    ChangeGroupKey.UPDATED,
    ChangeGroupKey.CORRECTED,
    ChangeGroupKey.EVIDENCE_UPDATED,
    ChangeGroupKey.MARKET_CONTEXT_UPDATED,
)

_GROUP_BY_TYPE = {
    ChangeType.NEW_FINDING: ChangeGroupKey.NEWLY_VERIFIED,
    ChangeType.FINDING_RETIRED: ChangeGroupKey.UPDATED,
    ChangeType.VALUE_CHANGED: ChangeGroupKey.UPDATED,
    ChangeType.STATE_CHANGED: ChangeGroupKey.UPDATED,
    ChangeType.CONFIDENCE_CHANGED: ChangeGroupKey.UPDATED,
    ChangeType.FRESHNESS_CHANGED: ChangeGroupKey.UPDATED,
    ChangeType.EVIDENCE_CHANGED: ChangeGroupKey.EVIDENCE_UPDATED,
    ChangeType.LIMITATION_CHANGED: ChangeGroupKey.EVIDENCE_UPDATED,
    ChangeType.CORRECTION: ChangeGroupKey.CORRECTED,
    ChangeType.CONFLICT_RESOLVED: ChangeGroupKey.CORRECTED,
    ChangeType.DIAGRAM_CHANGED: ChangeGroupKey.EVIDENCE_UPDATED,
    ChangeType.MEDIA_CHANGED: ChangeGroupKey.EVIDENCE_UPDATED,
    ChangeType.MARKET_CONTEXT_CHANGED: ChangeGroupKey.MARKET_CONTEXT_UPDATED,
}

_SUPPRESSED_TYPES = frozenset({ChangeType.WORDING_ONLY, ChangeType.NO_SEMANTIC_CHANGE})


@dataclass(frozen=True)
class CertifiedChangeDTO:
    change_id: str
    property_id: str
    audience: PresentationAudience
    change_type: ChangeType
    finding_key: str
    label: str
    before: str | None
    after: str | None
    materiality: ChangeMateriality
    detected_at: str
    source_diff_hash: str
    current_classification: str
    current_publication_scope: str
    historical_classification: str | None = None
    historical_publication_scope: str | None = None
    knowledge_change_only: bool = True

    def __post_init__(self) -> None:
        for name, value in (
            ("change_id", self.change_id),
            ("property_id", self.property_id),
            ("finding_key", self.finding_key),
            ("label", self.label),
            ("detected_at", self.detected_at),
            ("current_classification", self.current_classification),
            ("current_publication_scope", self.current_publication_scope),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} is required")
        if not isinstance(self.audience, PresentationAudience):
            raise ValueError("audience must be a PresentationAudience")
        if not isinstance(self.change_type, ChangeType):
            raise ValueError("change_type must be a ChangeType")
        if not isinstance(self.materiality, ChangeMateriality):
            raise ValueError("materiality must be a ChangeMateriality")
        if not _SHA256.fullmatch(self.source_diff_hash):
            raise ValueError("source_diff_hash must be lowercase sha256")
        if self.before is not None:
            if not self.historical_classification or not self.historical_publication_scope:
                raise ValueError("historical authorization metadata is required when before is present")


@dataclass(frozen=True)
class WhatChangedItem:
    change_id: str
    change_type: ChangeType
    finding_key: str
    label: str
    before: str | None
    after: str | None
    historical_value_withheld: bool
    materiality: ChangeMateriality
    detected_at: str
    knowledge_change_only: bool

    def canonical_payload(self) -> dict[str, object]:
        return {
            "change_id": self.change_id,
            "change_type": self.change_type.value,
            "finding_key": self.finding_key,
            "label": self.label,
            "before": self.before,
            "after": self.after,
            "historical_value_withheld": self.historical_value_withheld,
            "materiality": self.materiality.value,
            "detected_at": self.detected_at,
            "knowledge_change_only": self.knowledge_change_only,
        }


@dataclass(frozen=True)
class WhatChangedGroup:
    key: ChangeGroupKey
    title: str
    items: tuple[WhatChangedItem, ...]

    def canonical_payload(self) -> dict[str, object]:
        return {
            "key": self.key.value,
            "title": self.title,
            "items": [item.canonical_payload() for item in self.items],
        }


@dataclass(frozen=True)
class WhatChangedPanel:
    audience: PresentationAudience
    property_id: str
    title: str
    previous_semantic_fingerprint: str
    current_semantic_fingerprint: str
    source_diff_hash: str
    groups: tuple[WhatChangedGroup, ...]

    def canonical_payload(self) -> dict[str, object]:
        return {
            "audience": self.audience.value,
            "property_id": self.property_id,
            "title": self.title,
            "previous_semantic_fingerprint": self.previous_semantic_fingerprint,
            "current_semantic_fingerprint": self.current_semantic_fingerprint,
            "source_diff_hash": self.source_diff_hash,
            "groups": [group.canonical_payload() for group in self.groups],
        }

    @property
    def fingerprint(self) -> str:
        return sha256(canonical_json(self.canonical_payload()).encode("utf-8")).hexdigest()


class WhatChangedUi:
    """Present certified semantic changes without deriving or explaining them."""

    def build(
        self,
        *,
        audience: PresentationAudience,
        policy: AudiencePresentationPolicy,
        property_id: str,
        previous_semantic_fingerprint: str | None,
        current_semantic_fingerprint: str,
        changes: Iterable[CertifiedChangeDTO],
        has_previous_report: bool = True,
    ) -> WhatChangedPanel | None:
        if not isinstance(audience, PresentationAudience):
            raise ValueError("audience must be a PresentationAudience")
        if policy.audience is not audience:
            raise ValueError("audience policy mismatch")
        if not isinstance(property_id, str) or not property_id.strip():
            raise ValueError("property_id is required")
        if not _SHA256.fullmatch(current_semantic_fingerprint):
            raise ValueError("current_semantic_fingerprint must be lowercase sha256")
        if not has_previous_report:
            return None
        if previous_semantic_fingerprint is None or not _SHA256.fullmatch(previous_semantic_fingerprint):
            raise ValueError("previous_semantic_fingerprint must be lowercase sha256")

        records = tuple(changes)
        if not records:
            return None
        if any(not isinstance(change, CertifiedChangeDTO) for change in records):
            raise ValueError("WhatChangedUi requires CertifiedChangeDTO inputs")
        if any(change.property_id != property_id for change in records):
            raise ValueError("change history property identity mismatch")
        if any(change.audience is not audience for change in records):
            raise ValueError("change history audience mismatch")

        diff_hashes = {change.source_diff_hash for change in records}
        if len(diff_hashes) != 1:
            raise ValueError("change history source diff mismatch")
        source_diff_hash = next(iter(diff_hashes))

        visible: list[tuple[ChangeGroupKey, WhatChangedItem]] = []
        for change in records:
            policy.require_allowed(
                classification=change.current_classification,
                publication_scope=change.current_publication_scope,
            )

            if change.change_type in _SUPPRESSED_TYPES:
                continue
            if audience is not PresentationAudience.AGENT and change.materiality is ChangeMateriality.DETAIL:
                continue

            group = _GROUP_BY_TYPE.get(change.change_type)
            if group is None:
                raise ValueError(f"unsupported semantic change type: {change.change_type.value}")

            before = change.before
            withheld = False
            if before is not None:
                historical_allowed = policy.allows(
                    classification=str(change.historical_classification),
                    publication_scope=str(change.historical_publication_scope),
                )
                if not historical_allowed:
                    before = None
                    withheld = True

            visible.append(
                (
                    group,
                    WhatChangedItem(
                        change_id=change.change_id,
                        change_type=change.change_type,
                        finding_key=change.finding_key,
                        label=change.label,
                        before=before,
                        after=change.after,
                        historical_value_withheld=withheld,
                        materiality=change.materiality,
                        detected_at=change.detected_at,
                        knowledge_change_only=change.knowledge_change_only,
                    ),
                )
            )

        if not visible:
            return None
        if previous_semantic_fingerprint == current_semantic_fingerprint:
            raise ValueError("semantic change records cannot bind identical report fingerprints")

        grouped: list[WhatChangedGroup] = []
        for key in _GROUP_ORDER:
            items = tuple(
                sorted(
                    (item for group, item in visible if group is key),
                    key=lambda item: (item.label, item.finding_key, item.change_id),
                )
            )
            if items:
                grouped.append(WhatChangedGroup(key=key, title=_GROUP_TITLES[key], items=items))

        return WhatChangedPanel(
            audience=audience,
            property_id=property_id,
            title="What Changed",
            previous_semantic_fingerprint=previous_semantic_fingerprint,
            current_semantic_fingerprint=current_semantic_fingerprint,
            source_diff_hash=source_diff_hash,
            groups=tuple(grouped),
        )
