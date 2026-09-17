from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Mapping
from uuid import UUID
import yaml
from src.shared.canonical_json import canonical_json

@dataclass(frozen=True)
class EnvironmentParityPolicy:
    policy_version: str
    required_keys: tuple[str,...]
    exact_match_keys: tuple[str,...]

    @classmethod
    def load(cls, path: str | Path) -> 'EnvironmentParityPolicy':
        data = yaml.safe_load(Path(path).read_text())
        if data.get('status') != 'LOCKED':
            raise ValueError('environment parity policy must be LOCKED')
        required = tuple(data.get('required_keys') or ())
        exact = tuple(data.get('exact_match_keys') or ())
        if not required or not set(exact).issubset(set(required)):
            raise ValueError('invalid environment parity policy')
        return cls(str(data['policy_version']), required, exact)

@dataclass(frozen=True)
class EnvironmentParityResult:
    production_certification_id: UUID
    policy_version: str
    expected_fingerprint: str
    observed_fingerprint: str
    parity_status: str
    mismatch_keys: tuple[str,...]
    expected_environment: Mapping[str,str]
    observed_environment: Mapping[str,str]
    verifier_version: str
    verified_by: str

class EnvironmentParityVerifier:
    @staticmethod
    def _fingerprint(values: Mapping[str,str], keys: tuple[str,...]) -> str:
        payload = {k: values[k] for k in sorted(keys)}
        return sha256(canonical_json(payload).encode('utf-8')).hexdigest()

    def verify(self, *, production_certification_id: UUID, policy: EnvironmentParityPolicy,
               expected: Mapping[str,str], observed: Mapping[str,str], verifier_version: str,
               verified_by: str) -> EnvironmentParityResult:
        missing = sorted(k for k in policy.required_keys if k not in expected or k not in observed)
        mismatches = sorted(k for k in policy.exact_match_keys
                            if k in expected and k in observed and str(expected[k]) != str(observed[k]))
        mismatch_keys = tuple(sorted(set(missing + mismatches)))
        status = 'PASS' if not mismatch_keys else 'FAIL'
        if not verifier_version.strip() or not verified_by.strip():
            raise ValueError('verifier_version and verified_by are required')
        expected_complete = {k: str(expected.get(k,'')) for k in policy.required_keys}
        observed_complete = {k: str(observed.get(k,'')) for k in policy.required_keys}
        return EnvironmentParityResult(
            production_certification_id, policy.policy_version,
            self._fingerprint(expected_complete, policy.required_keys),
            self._fingerprint(observed_complete, policy.required_keys),
            status, mismatch_keys, expected_complete, observed_complete,
            verifier_version, verified_by,
        )
