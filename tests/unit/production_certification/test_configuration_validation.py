from pathlib import Path
from uuid import uuid4
from src.production_certification.configuration.validation import ProductionConfigurationPolicy, ProductionConfigurationValidator
ROOT=Path(__file__).resolve().parents[3]
POLICY=ROOT/'registries/production-certification/configuration-policy.yaml'
BASE={
'environment_name':'production','timezone':'UTC','database_ssl_required':True,'service_auth_required':True,
'public_delivery_read_only':True,'backup_verification_required':True,'post_restore_publication_freeze_required':True,
'shadow_publication_mutation_allowed':False,'canonical_serialization_version':'1.0.0','secrets_source':'vault',
'artifact_storage_backend':'s3-compatible','service_key_provider':'kms'
}
def test_production_configuration_passes_locked_safe_values():
    p=ProductionConfigurationPolicy.load(POLICY)
    r=ProductionConfigurationValidator().validate(production_certification_id=uuid4(),policy=p,observed=BASE,validator_version='1',validated_by='ops')
    assert r.status=='PASS' and r.violation_codes==()

def test_production_configuration_fails_closed_on_publish_shadow_or_inline_secret():
    p=ProductionConfigurationPolicy.load(POLICY); bad=dict(BASE); bad['shadow_publication_mutation_allowed']=True; bad['secrets_source']='inline'
    r=ProductionConfigurationValidator().validate(production_certification_id=uuid4(),policy=p,observed=bad,validator_version='1',validated_by='ops')
    assert r.status=='FAIL'
    assert 'MISMATCH:shadow_publication_mutation_allowed' in r.violation_codes
    assert 'PROHIBITED:secrets_source' in r.violation_codes

def test_production_configuration_missing_required_value_fails():
    p=ProductionConfigurationPolicy.load(POLICY); bad=dict(BASE); bad.pop('service_key_provider')
    r=ProductionConfigurationValidator().validate(production_certification_id=uuid4(),policy=p,observed=bad,validator_version='1',validated_by='ops')
    assert r.status=='FAIL' and 'MISSING:service_key_provider' in r.violation_codes
