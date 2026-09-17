from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import yaml

class AudiencePolicyRegistryError(ValueError):
    pass

@dataclass(frozen=True)
class AudiencePolicy:
    role_id: str
    report_variants: frozenset[str]
    required_classifications: frozenset[str]
    response_dto: str

class AudiencePolicyRegistry:
    EXPECTED_ID = "STH-AUDIENCE-POLICY-v1.0"
    EXPECTED_ROLES = frozenset({"PUBLIC","SELLER","AGENT","OPERATIONS","ADMIN"})
    EXPECTED_VARIANTS = frozenset({"PUBLIC","SELLER","AGENT"})

    def __init__(self, path: str | Path):
        raw = yaml.safe_load(Path(path).read_text())
        if raw.get("registry_id") != self.EXPECTED_ID or raw.get("status") != "LOCKED":
            raise AudiencePolicyRegistryError("AUDIENCE_POLICY_REGISTRY_INVALID")
        audiences = raw.get("audiences") or {}
        if set(audiences) != self.EXPECTED_ROLES:
            raise AudiencePolicyRegistryError("AUDIENCE_POLICY_ROLE_SET_INVALID")
        self.registry_id = raw["registry_id"]
        self.version = str(raw["version"])
        self._policies: dict[str, AudiencePolicy] = {}
        for role_id, item in audiences.items():
            variants = frozenset(item.get("report_variants") or [])
            if not variants or not variants <= self.EXPECTED_VARIANTS:
                raise AudiencePolicyRegistryError(f"AUDIENCE_POLICY_VARIANTS_INVALID:{role_id}")
            required = frozenset(item.get("required_classifications") or [])
            dto = item.get("response_dto")
            if not required or not dto:
                raise AudiencePolicyRegistryError(f"AUDIENCE_POLICY_INCOMPLETE:{role_id}")
            self._policies[role_id] = AudiencePolicy(role_id, variants, required, str(dto))

    def get(self, role_id: str) -> AudiencePolicy:
        try:
            return self._policies[role_id]
        except KeyError as exc:
            raise AudiencePolicyRegistryError("UNKNOWN_AUDIENCE_ROLE") from exc
