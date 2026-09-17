import pytest
from src.security.responses import NegativeFieldProtector, NegativeFieldViolation

def test_recursive_forbidden_field_detection():
    p=NegativeFieldProtector()
    hits=p.find_forbidden('PUBLIC',{'safe':1,'nested':[{'semantic_fingerprint':'x'}]})
    assert hits==('nested[0].semantic_fingerprint',)

def test_public_and_seller_reject_lineage_fields():
    p=NegativeFieldProtector()
    with pytest.raises(NegativeFieldViolation): p.require_clean('PUBLIC',{'lineage':{'snapshot_id':'x'}})
    with pytest.raises(NegativeFieldViolation): p.require_clean('SELLER',{'finding':{'source_snapshot_id':'x'}})

def test_agent_still_rejects_restricted_or_secret_fields():
    p=NegativeFieldProtector()
    with pytest.raises(NegativeFieldViolation): p.require_clean('AGENT',{'system_secret':'x'})
