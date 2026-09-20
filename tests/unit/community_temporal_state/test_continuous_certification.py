from dataclasses import fields
import pytest
from src.community_temporal_state.continuous_certification import *

REG="registries/community_temporal_state/m13-009-continuous-certification-v1.0.yaml"
def reg(): return load_continuous_certification_registry(REG)
KINDS=("COMMUNITY_SNAPSHOT","TEMPORAL_DELTA","TEMPORAL_HISTORY","PROMOTED_PATTERNS","SCENARIO_INTELLIGENCE","UNIFIED_SELLER_INTELLIGENCE","HISTORICAL_REPLAY")
def a(kind,state="CERTIFIED",seed="a",reason=None):
    return make_certification_artifact(artifact_kind=kind,artifact_id="A-"+kind,
      artifact_fingerprint=seed*64,artifact_state=state,lineage_fingerprint="b"*64,
      reason=reason,registry=reg())
def artifacts(overrides=None):
    overrides=overrides or {}
    return tuple(a(k,**overrides.get(k,{})) for k in KINDS)
def receipt(arts=None,drift=False,prior=None):
    return certify_intelligence_cycle(receipt_id="R1",property_id="P1",community_id="SAN-TAN-HEIGHTS",
      temporal_boundary="2026-09-20T10:00:00-07:00",artifacts=arts or artifacts(),registry=reg(),
      policy_version="M13-009-v1",prior_receipt_fingerprint=prior,drift_detected=drift)

def test_complete_clean_cycle_is_certified():
    r=receipt(); assert r.certification_state=="CERTIFIED" and not r.blocking_artifacts
def test_missing_required_artifact_blocks():
    r=receipt(tuple(x for x in artifacts() if x.artifact_kind!="HISTORICAL_REPLAY"))
    assert r.certification_state=="BLOCKED" and "HISTORICAL_REPLAY" in r.blocking_artifacts
def test_blocked_required_artifact_blocks_cycle():
    r=receipt(artifacts({"TEMPORAL_DELTA":{"state":"BLOCKED","reason":"Conflict."}}))
    assert r.certification_state=="BLOCKED" and "TEMPORAL_DELTA" in r.blocking_artifacts
def test_degraded_artifact_requires_review():
    r=receipt(artifacts({"HISTORICAL_REPLAY":{"state":"DEGRADED","reason":"Delayed input."}}))
    assert r.certification_state=="REVIEW_REQUIRED" and "HISTORICAL_REPLAY" in r.review_required_artifacts
def test_stale_artifact_requires_review():
    r=receipt(artifacts({"PROMOTED_PATTERNS":{"state":"STALE","reason":"Freshness window expired."}}))
    assert r.certification_state=="REVIEW_REQUIRED" and "PROMOTED_PATTERNS" in r.review_required_artifacts
def test_drift_requires_review_even_when_artifacts_certified():
    assert receipt(drift=True).certification_state=="REVIEW_REQUIRED"
def test_non_certified_state_requires_reason():
    with pytest.raises(ValueError,match="explicit reason"): a("TEMPORAL_DELTA",state="STALE")
def test_duplicate_artifact_kind_rejected():
    xs=artifacts()+(a("TEMPORAL_DELTA",seed="c"),)
    with pytest.raises(ValueError,match="duplicate artifact kind"): receipt(xs)
def test_unknown_artifact_kind_rejected():
    xs=artifacts()+(a("UNSUPPORTED"),)
    with pytest.raises(ValueError,match="unsupported certification artifact kind"): receipt(xs)
def test_prior_receipt_is_pinned_and_immutable():
    r=receipt(prior="c"*64); assert r.prior_receipt_fingerprint=="c"*64
def test_deterministic_replay_and_order_independence():
    xs=artifacts(); r=receipt(xs)
    assert validate_continuous_certification_replay(r,receipt_id="R1",property_id="P1",community_id="SAN-TAN-HEIGHTS",
      temporal_boundary="2026-09-20T10:00:00-07:00",artifacts=tuple(reversed(xs)),registry=reg(),
      policy_version="M13-009-v1",prior_receipt_fingerprint=None,drift_detected=False)
def test_no_prohibited_decision_or_execution_fields():
    forbidden={"recommendation","recommended_price","list_price","pricing_strategy","prediction","rank","seller_score",
      "contact_action","marketing_action","execution_action","valuation"}
    for cls in (CertificationArtifact,ContinuousCertificationReceipt):
        assert {f.name for f in fields(cls)}.isdisjoint(forbidden)
