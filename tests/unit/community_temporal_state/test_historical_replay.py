from dataclasses import fields
import pytest
from src.community_temporal_state.historical_replay import *

REG="registries/community_temporal_state/m13-008-historical-replay-v1.0.yaml"
def reg(): return load_historical_replay_registry(REG)
def c(cid="C1",cond="NORMAL",expected="a",observed="a",events=(),parent=None,regime="CALM"):
    return make_replay_case(case_id=cid,regime=regime,input_condition=cond,historical_input_fingerprint="f"*64,
      expected_output_fingerprint=None if expected is None else expected*64,
      observed_output_fingerprint=None if observed is None else observed*64,
      detector_event_ids=events,correction_parent_case_id=parent)

def test_normal_historical_replay_matches():
    r=evaluate_replay_case(c(),reg()); assert r.outcome=="MATCH" and r.reproducible
def test_drift_is_explicit():
    r=evaluate_replay_case(c(expected="a",observed="b"),reg()); assert r.outcome=="DRIFT" and not r.materiality_stable
def test_duplicate_events_measured():
    r=evaluate_replay_case(c(cond="DUPLICATE",events=("E1","E1")),reg()); assert r.duplicated_event_count==1 and r.outcome=="DEGRADED"
def test_corrected_case_requires_parent():
    with pytest.raises(ValueError,match="parent case id"): evaluate_replay_case(c(cond="CORRECTED",parent=None),reg())
def test_correction_parent_must_exist_in_report():
    with pytest.raises(ValueError,match="parent case missing"): build_replay_report(report_id="R1",cases=(c("C2","CORRECTED",parent="C1"),),registry=reg())
def test_delayed_input_is_degraded_not_hidden():
    assert evaluate_replay_case(c(cond="DELAYED"),reg()).outcome=="DEGRADED"
def test_conflicted_input_blocks_affected_replay():
    r=evaluate_replay_case(c(cond="CONFLICTED"),reg()); assert r.outcome=="BLOCKED" and r.conflict_explicit
def test_missing_input_is_explicit():
    r=evaluate_replay_case(c(cond="MISSING",expected="a",observed=None),reg()); assert r.outcome=="DEGRADED" and r.miss
def test_stale_input_is_degraded():
    assert evaluate_replay_case(c(cond="STALE"),reg()).outcome=="DEGRADED"
def test_rapid_market_regime_is_supported():
    assert evaluate_replay_case(c(regime="RAPID_CHANGE"),reg()).outcome=="MATCH"
def test_report_is_deterministic_and_counts_conditions():
    cases=(c("C1"),c("C2",expected="a",observed="b"),c("C3","DUPLICATE",events=("E1","E1")))
    r=build_replay_report(report_id="R1",cases=cases,registry=reg())
    assert r.drift_count==1 and r.duplication_count==1 and validate_replay_report(r,report_id="R1",cases=tuple(reversed(cases)),registry=reg())
def test_no_prohibited_autonomous_or_valuation_fields():
    forbidden={"recommended_price","list_price","seller_intent","protected_class","marketing_action","contact_action","execution_action","valuation"}
    for cls in (HistoricalReplayCase,HistoricalReplayResult,HistoricalReplayReport):
        assert {f.name for f in fields(cls)}.isdisjoint(forbidden)
