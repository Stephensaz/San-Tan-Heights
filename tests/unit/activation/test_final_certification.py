from copy import deepcopy

from src.activation.final_certification import (
    evaluate_final_certification,
    load_evidence_set,
    load_final_policy,
    run_repository_final_certification,
)
from pathlib import Path
import hashlib
import yaml


def loaded():
    root = Path(".")
    evidence, hashes = load_evidence_set(root)
    contract_path = root / "contracts/activation/STH-PRODUCTION-POPULATION-ACTIVATION-v1.0.yaml"
    policy_path = root / "registries/activation/m9-012-final-certification-v1.0.yaml"
    contract = yaml.safe_load(contract_path.read_text())
    policy = load_final_policy(policy_path)
    return evidence, hashes, contract, policy, hashlib.sha256(contract_path.read_bytes()).hexdigest(), hashlib.sha256(policy_path.read_bytes()).hexdigest()


def evaluate(evidence):
    _, hashes, contract, policy, contract_hash, policy_hash = loaded()
    return evaluate_final_certification(
        evidence=evidence,
        evidence_hashes=hashes,
        contract=contract,
        policy=policy,
        contract_hash=contract_hash,
        policy_hash=policy_hash,
    )


def test_repository_final_certification_is_pass_go():
    result = run_repository_final_certification(".")
    assert result.status == "PASS"
    assert result.verdict == "GO"
    assert len(result.candidate_fingerprint) == 64
    assert len(result.certification_root_hash) == 64
    assert not result.reason_codes
    assert all(v == "PASS" for v in result.check_statuses.values())


def test_result_is_deterministic():
    a = run_repository_final_certification(".")
    b = run_repository_final_certification(".")
    assert a.candidate_fingerprint == b.candidate_fingerprint
    assert a.certification_root_hash == b.certification_root_hash


def test_missing_ticket_acceptance_forces_no_go():
    evidence, *_ = loaded()
    mutated = deepcopy(evidence)
    mutated["M9-008"]["status"] = "BLOCKED"
    result = evaluate(mutated)
    assert result.status == "FAIL"
    assert result.verdict == "NO_GO"
    assert "M9-008_EVIDENCE_NOT_ACCEPTED" in result.reason_codes


def test_nonzero_hard_zero_defect_forces_no_go():
    evidence, *_ = loaded()
    mutated = deepcopy(evidence)
    mutated["M9-009"]["defects"]["tier_leakage_violations"] = 1
    result = evaluate(mutated)
    assert result.verdict == "NO_GO"
    assert "HARD_ZERO_tier_leakage_violations_NONZERO" in result.reason_codes


def test_waiver_forces_no_go():
    evidence, *_ = loaded()
    mutated = deepcopy(evidence)
    mutated["M9-010"]["waivers"] = 1
    result = evaluate(mutated)
    assert result.verdict == "NO_GO"
    assert "WAIVERS_PRESENT" in result.reason_codes


def test_replay_control_failure_forces_no_go():
    evidence, *_ = loaded()
    mutated = deepcopy(evidence)
    mutated["M9-011"]["controls"]["exact_pointer_rollback"] = False
    result = evaluate(mutated)
    assert result.verdict == "NO_GO"
    assert "REFRESH_REGEN_ROLLBACK_REPLAY_NOT_CERTIFIABLE" in result.reason_codes


def test_conditional_go_is_locked_off():
    evidence, hashes, contract, policy, contract_hash, policy_hash = loaded()
    mutated_contract = deepcopy(contract)
    mutated_contract["acceptance_model"]["allow_conditional_go"] = True
    result = evaluate_final_certification(
        evidence=evidence,
        evidence_hashes=hashes,
        contract=mutated_contract,
        policy=policy,
        contract_hash=contract_hash,
        policy_hash=policy_hash,
    )
    assert result.verdict == "NO_GO"
    assert "LOCKED_ACCEPTANCE_MODEL_WEAKENED" in result.reason_codes
