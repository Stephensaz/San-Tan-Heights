from uuid import uuid4
from src.production_certification.shadow.orchestrator import ShadowRunResult, ShadowTargetResult
from src.production_certification.shadow.tracking import ShadowCycleTracker


def _run(results, production_certification_id=None):
    return ShadowRunResult(production_certification_id or uuid4(),'shadow-v1','a'*64,
        'PASS' if all(r.status=='PASS' for r in results) else 'FAIL',tuple(results),'b'*64)


def test_shadow_cycle_tracking_is_deterministic_and_counts_targets():
    p1,p2=uuid4(),uuid4()
    rows=[
        ShadowTargetResult(p2,'PUBLIC','PASS','c'*64,'d'*64,{'same':True}),
        ShadowTargetResult(p1,'AGENT','FAIL',None,None,{'error_type':'RuntimeError'}),
    ]
    tracker=ShadowCycleTracker()
    fixed=uuid4()
    cert_id=uuid4()
    a=tracker.capture(cycle_number=2,run_result=_run(rows,cert_id),recorded_by='ops',shadow_cycle_id=fixed)
    b=tracker.capture(cycle_number=2,run_result=_run(list(reversed(rows)),cert_id),recorded_by='ops',shadow_cycle_id=fixed)
    assert a.cycle_fingerprint==b.cycle_fingerprint
    assert a.target_count==2 and a.passed_target_count==1 and a.failed_target_count==1
    assert a.cycle_status=='FAIL'
    assert [(x.property_id,x.variant) for x in a.target_results]==sorted([(p2,'PUBLIC'),(p1,'AGENT')],key=lambda x:(str(x[0]),x[1]))


def test_shadow_cycle_rejects_duplicate_target():
    p=uuid4(); r=ShadowTargetResult(p,'PUBLIC','PASS','c'*64,'d'*64,{})
    try:
        ShadowCycleTracker().capture(cycle_number=1,run_result=_run([r,r]),recorded_by='ops')
        assert False
    except ValueError as e:
        assert 'duplicate' in str(e)
