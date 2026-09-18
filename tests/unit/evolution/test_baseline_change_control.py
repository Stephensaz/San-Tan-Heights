import hashlib, json
from copy import deepcopy
import pytest
from src.evolution.baseline_change_control import (
    load_policy, load_baseline, create_change_request, create_candidate,
    verify_baseline_unchanged, authorize_promotion, rollback_target
)

P="registries/evolution/m10-001-baseline-change-control-v1.0.yaml"
B="certification-evidence/m10-001/san-tan-heights-production-baseline-v1.0.0.json"

def policy(): return load_policy(P)
def baseline(): return load_baseline(B)

def request(**kw):
    args=dict(policy=policy(),baseline=baseline(),change_request_id="CR-1",change_class="BUG_FIX",
              version_class="PATCH",component_class="CORE_REUSABLE",description="fix deterministic bug",
              impact_keys=["report","evidence"],emergency=False)
    args.update(kw); return create_change_request(**args)

def candidate(**kw):
    args=dict(policy=policy(),baseline=baseline(),request=request(),candidate_id="C-1",
              candidate_version="1.0.1",changed_artifacts={"src/x.py":"a"*64},
              structured_diff=["src/x.py"],blocking_exceptions=[])
    args.update(kw); return create_candidate(**args)

def test_baseline_is_accepted_immutable():
    b=baseline(); assert b.baseline_id=="SAN_TAN_HEIGHTS_PRODUCTION_BASELINE"; assert len(b.baseline_fingerprint)==64

def test_change_request_has_exact_parent_lineage_and_is_deterministic():
    a=request(); b=request(); assert a.parent_baseline_fingerprint==baseline().baseline_fingerprint
    assert a.request_fingerprint==b.request_fingerprint

def test_unclassified_change_fails_closed():
    with pytest.raises(ValueError,match="unclassified change"): request(change_class="WHATEVER")

def test_emergency_change_still_requires_governed_request():
    r=request(emergency=True,change_request_id="EM-1"); assert r.emergency is True; assert len(r.impact_keys)>0

def test_candidate_cannot_reuse_baseline_version():
    with pytest.raises(ValueError,match="must differ"): candidate(candidate_version="1.0.0")

def test_candidate_has_deterministic_recertification_scope():
    c=candidate(); assert c.recertification_scope==("OWNING_COMPONENT","REGRESSION")
    assert c.promotion_eligible is True

def test_blocking_exception_prevents_promotion():
    c=candidate(blocking_exceptions=["BLOCK-1"]); assert c.promotion_eligible is False
    with pytest.raises(ValueError,match="blocking exceptions"): authorize_promotion(candidate=c,required_evidence={"REGRESSION":"PASS"},policy=policy())

def test_failed_evidence_prevents_promotion():
    with pytest.raises(ValueError,match="has not passed"):
        authorize_promotion(candidate=candidate(),required_evidence={"REGRESSION":"FAIL"},policy=policy())

def test_promotion_requires_evidence():
    with pytest.raises(ValueError,match="evidence required"):
        authorize_promotion(candidate=candidate(),required_evidence={},policy=policy())

def test_exact_rollback_only():
    b=baseline(); assert rollback_target(exact_baseline=b,requested_fingerprint=b.baseline_fingerprint)==b
    with pytest.raises(ValueError,match="exact certified baseline"): rollback_target(exact_baseline=b,requested_fingerprint="0"*64)

def test_baseline_mutation_is_detected(tmp_path):
    raw=open(B,"rb").read(); p=tmp_path/"baseline.json"; p.write_bytes(raw)
    fp=hashlib.sha256(raw).hexdigest(); verify_baseline_unchanged(baseline_path=p,frozen_fingerprint=fp)
    data=json.loads(p.read_text()); data["build_version"]="MUTATED"; p.write_text(json.dumps(data))
    with pytest.raises(ValueError,match="baseline mutation"): verify_baseline_unchanged(baseline_path=p,frozen_fingerprint=fp)
