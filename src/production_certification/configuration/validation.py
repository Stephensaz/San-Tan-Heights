from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Mapping
from uuid import UUID
import yaml
from src.shared.canonical_json import canonical_json

@dataclass(frozen=True)
class ProductionConfigurationPolicy:
    policy_version: str
    required_values: Mapping[str,str]
    prohibited_values: Mapping[str,tuple[str,...]]
    required_nonempty: tuple[str,...]

    @classmethod
    def load(cls, path: str | Path) -> 'ProductionConfigurationPolicy':
        data=yaml.safe_load(Path(path).read_text())
        if data.get('status') != 'LOCKED':
            raise ValueError('production configuration policy must be LOCKED')
        required={str(k):str(v) for k,v in (data.get('required_values') or {}).items()}
        prohibited={str(k):tuple(str(x) for x in v) for k,v in (data.get('prohibited_values') or {}).items()}
        nonempty=tuple(str(x) for x in (data.get('required_nonempty') or ()))
        if not required or not str(data.get('policy_version','')).strip():
            raise ValueError('invalid production configuration policy')
        return cls(str(data['policy_version']),required,prohibited,nonempty)

@dataclass(frozen=True)
class ProductionConfigurationResult:
    production_certification_id: UUID
    policy_version: str
    configuration_fingerprint: str
    status: str
    violation_codes: tuple[str,...]
    observed_configuration: Mapping[str,str]
    validator_version: str
    validated_by: str

class ProductionConfigurationValidator:
    def validate(self, *, production_certification_id: UUID, policy: ProductionConfigurationPolicy,
                 observed: Mapping[str,object], validator_version: str, validated_by: str) -> ProductionConfigurationResult:
        if not validator_version.strip() or not validated_by.strip():
            raise ValueError('validator_version and validated_by are required')
        normalized={str(k):str(v).lower() if isinstance(v,bool) else str(v) for k,v in observed.items()}
        violations=[]
        for key, expected in policy.required_values.items():
            if key not in normalized:
                violations.append(f'MISSING:{key}')
            elif normalized[key] != expected:
                violations.append(f'MISMATCH:{key}')
        for key in policy.required_nonempty:
            if not normalized.get(key,'').strip():
                violations.append(f'MISSING:{key}')
        for key, bad_values in policy.prohibited_values.items():
            if normalized.get(key) in bad_values:
                violations.append(f'PROHIBITED:{key}')
        payload={k:normalized[k] for k in sorted(normalized)}
        fp=sha256(canonical_json(payload).encode('utf-8')).hexdigest()
        return ProductionConfigurationResult(
            production_certification_id,policy.policy_version,fp,
            'PASS' if not violations else 'FAIL',tuple(sorted(set(violations))),payload,
            validator_version,validated_by,
        )
