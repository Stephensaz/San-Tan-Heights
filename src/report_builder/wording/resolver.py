from __future__ import annotations
from dataclasses import dataclass
from src.snapshot.repository.models import SnapshotFindingRecord


class ApprovedWordingError(ValueError):
    pass


@dataclass(frozen=True)
class ResolvedWording:
    text: str
    version: str


class ApprovedWordingResolver:
    _ATTRS = {
        "AGENT": ("agent_wording", "agent_wording_version"),
        "SELLER": ("seller_wording", "seller_wording_version"),
        "PUBLIC": ("public_wording", "public_wording_version"),
    }

    def resolve(self, finding: SnapshotFindingRecord, variant: str) -> ResolvedWording:
        try:
            text_attr, version_attr = self._ATTRS[variant]
        except KeyError as exc:
            raise ApprovedWordingError(f"unsupported report variant: {variant}") from exc
        text = getattr(finding, text_attr)
        version = getattr(finding, version_attr)
        if text is None or not str(text).strip():
            raise ApprovedWordingError(
                f"missing approved {variant} wording for finding {finding.finding_id}"
            )
        if version is None or not str(version).strip():
            raise ApprovedWordingError(
                f"missing approved {variant} wording version for finding {finding.finding_id}"
            )
        return ResolvedWording(str(text), str(version))
