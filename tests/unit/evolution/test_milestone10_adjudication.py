from copy import deepcopy
from pathlib import Path
import json

import pytest

from src.evolution.milestone10_adjudication import (
    execute_final_adjudication,
    load_adjudication_registry,
)

REGISTRY="registries/evolution/m10-010-final-adjudication-v1.0.yaml"


def registry():
    return load_adjudication_registry(REGISTRY)


def adjudicate(r=None):
    return execute_final_adjudication(repository_root=".",registry=r or registry())


def test_exact_m10_001_through_009_chain_is_registered():
    r=registry()
    assert list(r["accepted_evidence"])==[f"M10-{i:03d}" for i in range(1,10)]


def test_final_adjudication_replays_factory_and_portfolio_and_passes():
    result=adjudicate()
    assert result.status=="PASS"
    assert result.decision=="PLATFORM RELEASED"
    assert len(result.ticket_receipts)==9
    assert set(result.factory_replay_fingerprints)=={"RANCHO_VISTOSO","DAYBREAK_UT"}
    assert result.portfolio_decision=="GO"
    assert result.blocking_reasons==()
    assert result.certification_root_hash=="7c74fd81bcc91816dceb81129d022e6605b65ea5f1e14ab88ec8d8b75b005913"


def test_final_certification_root_is_deterministic():
    a=adjudicate()
    b=adjudicate()
    assert a.certification_root_hash==b.certification_root_hash
    assert a.portfolio_fingerprint==b.portfolio_fingerprint
    assert a.factory_replay_fingerprints==b.factory_replay_fingerprints


def test_every_accepted_evidence_has_zero_waivers_and_defects():
    result=adjudicate()
    assert all(x.status=="ACCEPTED" for x in result.ticket_receipts)
    assert all(x.waivers==0 for x in result.ticket_receipts)
    assert all(x.open_defects==0 for x in result.ticket_receipts)


def test_missing_evidence_forces_no_go(tmp_path):
    r=deepcopy(registry())
    r["accepted_evidence"]["M10-009"]="certification-evidence/m10-009/does-not-exist.json"
    result=adjudicate(r)
    assert result.status=="FAIL"
    assert result.decision=="NO-GO"
    assert "M10-009:EVIDENCE_MISSING" in result.blocking_reasons
    assert "EVIDENCE_CHAIN_INCOMPLETE" in result.blocking_reasons


def test_nonaccepted_evidence_forces_no_go(tmp_path):
    original=json.loads(Path("certification-evidence/m10-009/portfolio-certification-acceptance-v1.0.json").read_text())
    original["status"]="IN_PROGRESS"
    bad=tmp_path/"bad.json"
    bad.write_text(json.dumps(original))
    r=deepcopy(registry())
    r["accepted_evidence"]["M10-009"]=str(bad)
    result=adjudicate(r)
    assert result.decision=="NO-GO"
    assert "M10-009:NOT_ACCEPTED" in result.blocking_reasons


def test_waiver_forces_no_go(tmp_path):
    original=json.loads(Path("certification-evidence/m10-008/community-factory-acceptance-v1.0.json").read_text())
    original["waivers"]=1
    bad=tmp_path/"waiver.json"
    bad.write_text(json.dumps(original))
    r=deepcopy(registry())
    r["accepted_evidence"]["M10-008"]=str(bad)
    result=adjudicate(r)
    assert result.decision=="NO-GO"
    assert "M10-008:WAIVERS_PRESENT" in result.blocking_reasons


def test_open_defect_forces_no_go(tmp_path):
    original=json.loads(Path("certification-evidence/m10-007/daybreak-cold-start-acceptance-v1.0.json").read_text())
    original["open_defects"]=1
    bad=tmp_path/"defect.json"
    bad.write_text(json.dumps(original))
    r=deepcopy(registry())
    r["accepted_evidence"]["M10-007"]=str(bad)
    result=adjudicate(r)
    assert result.decision=="NO-GO"
    assert "M10-007:OPEN_DEFECTS_PRESENT" in result.blocking_reasons


def test_release_candidate_version_mismatch_fails_closed():
    r=deepcopy(registry())
    r["release_candidate_version"]="9.9.9"
    with pytest.raises(ValueError,match="release candidate version mismatch"):
        adjudicate(r)



def test_frozen_root_mismatch_forces_no_go():
    r=deepcopy(registry())
    r["expected_certification_root_hash"]="0"*64
    result=adjudicate(r)
    assert result.status=="FAIL"
    assert result.decision=="NO-GO"
    assert "CERTIFICATION_ROOT_MISMATCH" in result.blocking_reasons
