from pathlib import Path
from uuid import uuid4
from src.production_certification.environment.parity import EnvironmentParityPolicy, EnvironmentParityVerifier

ROOT=Path(__file__).resolve().parents[3]
POLICY=ROOT/'registries/production-certification/environment-parity.yaml'
BASE={
 'application_version':'0.1.39','python_major_minor':'3.13','postgres_major':'16','timezone':'UTC','locale':'C.UTF-8',
 'canonical_serialization_version':'1.0.0','production_certification_contract_version':'1.0.0'
}

def test_environment_parity_passes_exact_required_values():
    policy=EnvironmentParityPolicy.load(POLICY)
    result=EnvironmentParityVerifier().verify(production_certification_id=uuid4(),policy=policy,expected=BASE,observed=dict(BASE),verifier_version='1',verified_by='ops')
    assert result.parity_status=='PASS' and result.mismatch_keys==()
    assert result.expected_fingerprint==result.observed_fingerprint


def test_environment_parity_fails_on_material_drift():
    policy=EnvironmentParityPolicy.load(POLICY); observed=dict(BASE); observed['postgres_major']='17'
    result=EnvironmentParityVerifier().verify(production_certification_id=uuid4(),policy=policy,expected=BASE,observed=observed,verifier_version='1',verified_by='ops')
    assert result.parity_status=='FAIL'
    assert result.mismatch_keys==('postgres_major',)


def test_environment_parity_fails_when_required_key_missing():
    policy=EnvironmentParityPolicy.load(POLICY); observed=dict(BASE); observed.pop('locale')
    result=EnvironmentParityVerifier().verify(production_certification_id=uuid4(),policy=policy,expected=BASE,observed=observed,verifier_version='1',verified_by='ops')
    assert result.parity_status=='FAIL' and 'locale' in result.mismatch_keys
