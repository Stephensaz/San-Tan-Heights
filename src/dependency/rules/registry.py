from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import yaml

_ALLOWED_DECISIONS = frozenset({'NO_IMPACT','DIRTY','BLOCKED','INVALIDATION_REQUIRED','REVIEW_REQUIRED'})
_ALLOWED_VARIANTS = frozenset({'AGENT','SELLER','PUBLIC'})

class DependencyImpactRuleError(ValueError):
    pass

@dataclass(frozen=True)
class DependencyImpactRule:
    rule_id: str
    dependency_type: str
    variants: dict[str, bool]
    normal_change: str
    blocked_change: str
    invalidating_change: str
    requires_consumption: bool

class DependencyImpactRuleRegistry:
    def __init__(self, path: str|Path|None=None, dependency_types_path: str|Path|None=None):
        root = Path(__file__).resolve().parents[3]
        path = Path(path) if path else root/'registries/dependency-impact/rules-v1.0.yaml'
        dependency_types_path = Path(dependency_types_path) if dependency_types_path else root/'registries/dependency-types.yaml'
        raw = yaml.safe_load(path.read_text()) or {}
        allowed_types = set((yaml.safe_load(dependency_types_path.read_text()) or {}).get('types', ()))
        seen_ids, seen_types, rules = set(), set(), {}
        for item in raw.get('rules', ()):
            rid, dtype = item.get('rule_id'), item.get('dependency_type')
            variants = item.get('variants') or {}
            if not rid or rid in seen_ids:
                raise DependencyImpactRuleError(f'duplicate/empty rule_id: {rid}')
            if dtype not in allowed_types:
                raise DependencyImpactRuleError(f'unknown dependency type: {dtype}')
            if dtype in seen_types:
                raise DependencyImpactRuleError(f'duplicate dependency rule: {dtype}')
            if set(variants) != _ALLOWED_VARIANTS or any(not isinstance(v, bool) for v in variants.values()):
                raise DependencyImpactRuleError(f'invalid variants: {rid}')
            for field in ('normal_change','blocked_change','invalidating_change'):
                if item.get(field) not in _ALLOWED_DECISIONS:
                    raise DependencyImpactRuleError(f'invalid decision: {rid}:{field}')
            rule = DependencyImpactRule(rid, dtype, dict(variants), item['normal_change'], item['blocked_change'],
                                        item['invalidating_change'], bool(item.get('requires_consumption')))
            rules[dtype] = rule
            seen_ids.add(rid); seen_types.add(dtype)
        missing = (allowed_types - {'TEST_DEP'}) - set(rules)
        if missing:
            raise DependencyImpactRuleError('missing rules: ' + ','.join(sorted(missing)))
        self.registry_id = raw.get('registry_id')
        self.version = str(raw.get('version'))
        self._rules = rules

    def get(self, dependency_type: str) -> DependencyImpactRule:
        try:
            return self._rules[dependency_type]
        except KeyError as exc:
            raise DependencyImpactRuleError(f'no impact rule for dependency type: {dependency_type}') from exc

    @property
    def rules(self):
        return tuple(self._rules[k] for k in sorted(self._rules))
