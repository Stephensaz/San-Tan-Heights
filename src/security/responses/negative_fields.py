from __future__ import annotations
from typing import Any

class NegativeFieldViolation(ValueError):
    pass

# Deny lists are defense in depth. DTO whitelist construction remains the primary control.
FORBIDDEN_BY_AUDIENCE = {
    "PUBLIC": frozenset({
        "snapshot_id", "lineage", "dependency_manifest_hash", "semantic_fingerprint",
        "source_snapshot_id", "confidence_label", "evidence_disclosures", "detail",
        "report_schema_version", "content_contract_version", "variant_policy_version",
        "market_data_through", "builder_data_through",
        "passport_id", "passport_version", "internal_notes", "qa_status", "production_status",
    }),
    "SELLER": frozenset({
        "snapshot_id", "lineage", "dependency_manifest_hash", "semantic_fingerprint",
        "source_snapshot_id", "detail", "report_schema_version", "content_contract_version",
        "variant_policy_version", "passport_id", "passport_version", "internal_notes",
        "qa_status", "production_status",
    }),
    "AGENT": frozenset({"internal_notes", "restricted_value", "system_secret", "auth_token"}),
}

class NegativeFieldProtector:
    def forbidden(self, audience: str) -> frozenset[str]:
        try:
            return FORBIDDEN_BY_AUDIENCE[audience]
        except KeyError as exc:
            raise NegativeFieldViolation("UNKNOWN_RESPONSE_AUDIENCE") from exc

    def find_forbidden(self, audience: str, value: Any) -> tuple[str, ...]:
        forbidden = self.forbidden(audience)
        hits: list[str] = []
        def walk(node: Any, path: str) -> None:
            if isinstance(node, dict):
                for key, child in node.items():
                    p = f"{path}.{key}" if path else key
                    if key in forbidden: hits.append(p)
                    walk(child, p)
            elif isinstance(node, (list, tuple)):
                for idx, child in enumerate(node): walk(child, f"{path}[{idx}]")
        walk(value, "")
        return tuple(sorted(hits))

    def require_clean(self, audience: str, value: Any) -> None:
        hits = self.find_forbidden(audience, value)
        if hits:
            raise NegativeFieldViolation("FORBIDDEN_RESPONSE_FIELDS:" + ",".join(hits))
