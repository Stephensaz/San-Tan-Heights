from copy import deepcopy

from src.listing_execution.final_certification import (
    execute_final_certification,
    load_final_certification_registry,
)

R="registries/listing_execution/m12-009-final-certification-v1.0.yaml"

def reg(): return load_final_certification_registry(R)
def run(r=None): return execute_final_certification(repository_root=".",registry=r or reg())

def test_exact_a_through_j_sequence_is_frozen():
    assert [x.split("_",1)[0] for x in reg()["stages"]]==[f"M12-009{c}" for c in "ABCDEFGHIJ"]

def test_full_final_certification_passes_and_issues_real_go_decision():
    x=run()
    assert x.status=="PASS"
    assert x.decision=="GO"
    assert len(x.stage_results)==10
    assert all(s.status=="PASS" for s in x.stage_results)
    assert x.blocking_reasons==()
    assert x.certification_root_hash=="e56a8d039c4e0324ff694d0ea8cd5a190f48be6bb8b761d761a41f8af96e2a35"

def test_all_required_coverage_is_closed():
    x=run()
    assert set(x.coverage)==set(reg()["required_coverage"])

def test_m12_008_operational_root_reproduces_exactly():
    x=run()
    assert x.m12_008_operational_root==reg()["expected_m12_008"]["operational_certification_root"]

def test_final_certification_is_deterministic():
    assert run().certification_root_hash==run().certification_root_hash

def test_wrong_m12_008_root_forces_no_go():
    r=deepcopy(reg())
    r["expected_m12_008"]["operational_certification_root"]="0"*64
    x=run(r)
    assert x.status=="FAIL"
    assert x.decision=="NO-GO"
    assert any("M12_008_ROOT" in b or "M12-008" in b for b in x.blocking_reasons)

def test_missing_coverage_forces_no_go():
    r=deepcopy(reg())
    r["required_coverage"].append("IMPOSSIBLE_REQUIRED_CONTROL")
    x=run(r)
    assert x.status=="FAIL"
    assert "COVERAGE_MISSING:IMPOSSIBLE_REQUIRED_CONTROL" in x.blocking_reasons

def test_no_m12_009k_exists_in_stage_sequence():
    assert all(not x.startswith("M12-009K") for x in reg()["stages"])


def test_wrong_frozen_final_root_forces_no_go():
    r=deepcopy(reg())
    r["expected_certification_root_hash"]="0"*64
    x=run(r)
    assert x.status=="FAIL"
    assert x.decision=="NO-GO"
    assert "M12_FINAL_CERTIFICATION_ROOT_MISMATCH" in x.blocking_reasons
