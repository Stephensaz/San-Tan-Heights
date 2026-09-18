from copy import deepcopy

import json
from pathlib import Path
import pytest

from src.seller_intelligence.production_certification import (
    execute_production_certification,
    load_production_certification_registry,
)

R="registries/seller_intelligence/m11-009-production-certification-v1.0.yaml"


def reg():
    return load_production_certification_registry(R)


def certify(r=None):
    return execute_production_certification(repository_root=".",registry=r or reg())


def test_exact_m11_001_through_008_chain_registered():
    assert list(reg()["accepted_evidence"])==[f"M11-{i:03d}" for i in range(1,9)]


def test_complete_chain_replays_as_production_candidate_not_final_release():
    result=certify()
    assert result.status=="PASS"
    assert result.decision=="PRODUCTION CANDIDATE"
    assert result.blocking_reasons==()
    assert len(result.evidence_receipts)==8
    assert result.end_to_end_fingerprint
    assert result.promotion_package_fingerprint
    assert result.rollback_rule_fingerprint
    assert result.public_eligible is False
    assert result.external_action_capability=="NONE"
    assert result.production_candidate_root=="2cca3529c4b09b0a3dc4305b9b7c1732b894fc47018dc971cfe18a98c8e269dd"


def test_production_candidate_root_is_deterministic():
    assert certify().production_candidate_root==certify().production_candidate_root


def test_all_evidence_is_accepted_zero_waivers_zero_defects():
    result=certify()
    assert all(x.status=="ACCEPTED" for x in result.evidence_receipts)
    assert all(x.waivers==0 for x in result.evidence_receipts)
    assert all(x.open_defects==0 for x in result.evidence_receipts)


def test_negative_controls_are_complete():
    result=certify()
    assert set(result.negative_controls)=={
        "UNCERTIFIED_INPUT_FAILS_CLOSED",
        "PUBLIC_STRATEGY_LEAKAGE_PROHIBITED",
        "REGRESSION_BLOCKS_PROMOTION",
    }


def test_missing_evidence_forces_no_go():
    r=deepcopy(reg())
    r["accepted_evidence"]["M11-008"]="certification-evidence/m11-008/missing.json"
    result=certify(r)
    assert result.status=="FAIL"
    assert result.decision=="NO-GO"
    assert "M11-008:EVIDENCE_MISSING" in result.blocking_reasons


def test_nonaccepted_evidence_forces_no_go(tmp_path):
    data=json.loads(Path("certification-evidence/m11-008/calibration-promotion-acceptance-v1.0.json").read_text())
    data["status"]="IN_PROGRESS"
    p=tmp_path/"bad.json"; p.write_text(json.dumps(data))
    r=deepcopy(reg()); r["accepted_evidence"]["M11-008"]=str(p)
    result=certify(r)
    assert "M11-008:NOT_ACCEPTED" in result.blocking_reasons


def test_waiver_forces_no_go(tmp_path):
    data=json.loads(Path("certification-evidence/m11-007/effectiveness-learning-acceptance-v1.0.json").read_text())
    data["waivers"]=1
    p=tmp_path/"bad.json"; p.write_text(json.dumps(data))
    r=deepcopy(reg()); r["accepted_evidence"]["M11-007"]=str(p)
    assert "M11-007:WAIVERS_PRESENT" in certify(r).blocking_reasons


def test_open_defect_forces_no_go(tmp_path):
    data=json.loads(Path("certification-evidence/m11-006/seller-workspace-acceptance-v1.0.json").read_text())
    data["open_defects"]=1
    p=tmp_path/"bad.json"; p.write_text(json.dumps(data))
    r=deepcopy(reg()); r["accepted_evidence"]["M11-006"]=str(p)
    assert "M11-006:OPEN_DEFECTS_PRESENT" in certify(r).blocking_reasons


def test_wrong_candidate_version_fails_closed():
    r=deepcopy(reg()); r["production_candidate_version"]="9.9.9"
    with pytest.raises(ValueError,match="production candidate version mismatch"):
        certify(r)



def test_frozen_production_candidate_root_mismatch_fails_closed():
    r=deepcopy(reg())
    r["expected_production_candidate_root"]="0"*64
    with pytest.raises(ValueError,match="accepted production candidate root mismatch"):
        certify(r)
