from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import yaml

VARIANTS = ('AGENT','SELLER','PUBLIC')
PUBLICATION_SCOPES = frozenset({'AGENT','SELLER','PUBLIC','AGENT_SELLER','ALL','NONE'})
VALID_EVIDENCE_DEPTH = frozenset({'DETAILED','STANDARD','LIGHT'})
VALID_CONFIDENCE = frozenset({'DETAILED','FRIENDLY','SELECTIVE'})

class VariantPolicyRegistryError(ValueError):
    pass

@dataclass(frozen=True)
class VariantPolicy:
    policy_id: str
    version: str
    variant: str
    allowed_classifications: frozenset[str]
    allowed_publication_scopes: frozenset[str]
    evidence_depth: str
    confidence_visibility: str
    required_sections: tuple[str,...]
    optional_sections: tuple[str,...]
    prohibited_finding_types: frozenset[str]

    def allows_classification(self, classification: str) -> bool:
        return classification in self.allowed_classifications

    def allows_publication_scope(self, scope: str) -> bool:
        return scope in self.allowed_publication_scopes

class VariantPolicyRegistry:
    def __init__(self, policies: dict[str, VariantPolicy]):
        self._policies = policies

    @classmethod
    def from_repository(cls, root: Path) -> 'VariantPolicyRegistry':
        root = Path(root)
        class_raw = yaml.safe_load((root/'registries/classifications/data-classifications.yaml').read_text())
        known_classifications = set(class_raw['classifications'])
        policies = {}
        for variant in VARIANTS:
            path = root/'registries/report-variants'/f'{variant.lower()}.yaml'
            raw = yaml.safe_load(path.read_text())
            if raw.get('variant') != variant:
                raise VariantPolicyRegistryError(f'{path.name} variant mismatch')
            if variant in policies:
                raise VariantPolicyRegistryError(f'duplicate variant policy: {variant}')
            allowed_cls = frozenset(raw.get('allowed_classifications') or [])
            unknown_cls = allowed_cls - known_classifications
            if unknown_cls:
                raise VariantPolicyRegistryError(f'unknown classifications for {variant}: {sorted(unknown_cls)}')
            scopes = frozenset(raw.get('allowed_publication_scopes') or [])
            unknown_scopes = scopes - PUBLICATION_SCOPES
            if unknown_scopes:
                raise VariantPolicyRegistryError(f'unknown publication scopes for {variant}: {sorted(unknown_scopes)}')
            depth = str(raw.get('evidence_depth'))
            confidence = str(raw.get('confidence_visibility'))
            if depth not in VALID_EVIDENCE_DEPTH:
                raise VariantPolicyRegistryError(f'unknown evidence depth: {depth}')
            if confidence not in VALID_CONFIDENCE:
                raise VariantPolicyRegistryError(f'unknown confidence visibility: {confidence}')
            required = tuple(raw.get('required_sections') or [])
            optional = tuple(raw.get('optional_sections') or [])
            if set(required) & set(optional):
                raise VariantPolicyRegistryError(f'required/optional section overlap for {variant}')
            policies[variant] = VariantPolicy(
                str(raw['policy_id']), str(raw['version']), variant, allowed_cls, scopes,
                depth, confidence, required, optional, frozenset(raw.get('prohibited_finding_types') or [])
            )
        if set(policies) != set(VARIANTS):
            raise VariantPolicyRegistryError('policies must exist for AGENT, SELLER, and PUBLIC')
        return cls(policies)

    def get(self, variant: str) -> VariantPolicy:
        try:
            return self._policies[variant]
        except KeyError as exc:
            raise VariantPolicyRegistryError(f'unsupported report variant: {variant}') from exc

    @property
    def variants(self) -> tuple[str,...]:
        return tuple(VARIANTS)
