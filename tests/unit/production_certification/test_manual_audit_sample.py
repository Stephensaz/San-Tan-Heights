from pathlib import Path
from uuid import uuid4
from src.production_certification.audit.sample import ManualAuditPolicy, ManualAuditSampleBuilder
from src.production_certification.shadow.orchestrator import ShadowRunResult, ShadowTargetResult
from src.production_certification.shadow.tracking import ShadowCycleTracker

ROOT=Path(__file__).resolve().parents[3]
POLICY=ROOT/'registries/production-certification/manual-audit-policy.yaml'


def _cycle(props, failed):
    results=[]
    for p in props:
        status='FAIL' if p in failed else 'PASS'
        results.append(ShadowTargetResult(p,'PUBLIC',status,'c'*64 if status=='PASS' else None,'d'*64 if status=='PASS' else None,{}))
    run=ShadowRunResult(uuid4(),'shadow-v1','a'*64,'FAIL' if failed else 'PASS',tuple(results),'b'*64)
    return ShadowCycleTracker().capture(cycle_number=1,run_result=run,recorded_by='ops',shadow_cycle_id=uuid4())


def test_sample_is_reproducible_and_prioritizes_failed_shadow_properties():
    policy=ManualAuditPolicy.load(POLICY)
    props=[uuid4() for _ in range(20)]; failed={props[4],props[9]}
    cycle=_cycle(props,failed)
    builder=ManualAuditSampleBuilder(); fixed=uuid4()
    a=builder.build(policy=policy,shadow_cycle=cycle,pilot_property_ids=reversed(props),built_by='reviewer',manual_audit_sample_id=fixed)
    b=builder.build(policy=policy,shadow_cycle=cycle,pilot_property_ids=props,built_by='reviewer',manual_audit_sample_id=fixed)
    assert a.sample_fingerprint==b.sample_fingerprint
    assert len(a.sampled_property_ids)==10
    assert failed.issubset(set(a.sampled_property_ids))


def test_sample_rejects_shadow_property_outside_pilot():
    policy=ManualAuditPolicy.load(POLICY)
    p=uuid4(); cycle=_cycle([p],set())
    try:
        ManualAuditSampleBuilder().build(policy=policy,shadow_cycle=cycle,pilot_property_ids=[uuid4()],built_by='reviewer')
        assert False
    except ValueError as e:
        assert 'outside frozen pilot' in str(e)
