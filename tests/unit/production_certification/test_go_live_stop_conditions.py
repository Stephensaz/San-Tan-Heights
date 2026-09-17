from uuid import uuid4
from src.production_certification.go_live.stop_conditions import GoLiveStopPolicy, GoLiveObservedState, GoLiveStopConditionEngine
P='registries/production-certification/go-live-stop-policy.yaml'

def clean():
    return GoLiveObservedState('PASS','PASS','PASS',0,0,False,False,'a'*64,'a'*64)

def test_clean_state_is_clear():
    r=GoLiveStopConditionEngine().evaluate(production_certification_id=uuid4(),policy=GoLiveStopPolicy.load(P),observed=clean(),evaluated_by='ops')
    assert r.status=='CLEAR' and r.blocking_conditions==()

def test_any_go_live_stop_is_fail_closed_and_all_active_reasons_are_reported():
    o=GoLiveObservedState('FAIL','PASS','FAIL',1,2,True,True,'a'*64,'b'*64)
    r=GoLiveStopConditionEngine().evaluate(production_certification_id=uuid4(),policy=GoLiveStopPolicy.load(P),observed=o,evaluated_by='ops')
    assert r.status=='STOP'
    assert set(r.blocking_conditions)=={'ENVIRONMENT_PARITY_NOT_PASS','SHADOW_ACCEPTANCE_NOT_PASS','HARD_ZERO_METRIC_NONZERO','OPEN_CRITICAL_INCIDENT','GLOBAL_PUBLICATION_FREEZE_ACTIVE','CANDIDATE_REVOKED','CANDIDATE_FINGERPRINT_MISMATCH'}
