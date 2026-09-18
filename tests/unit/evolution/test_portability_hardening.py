from copy import deepcopy
from hashlib import sha256
from pathlib import Path

import pytest

from src.evolution.portability_pilot import load_pilot_profile
from src.evolution.portability_profiles import (
    load_governed_profile,
    load_hardening_registry,
    validate_disposition_artifacts,
)
from src.evolution.portability_hardening import execute_hardened_replay

REGISTRY="registries/evolution/m10-006-portability-hardening-v1.0.yaml"
PROFILE="config/pilots/rancho_vistoso/portability-pilot-v1.0.yaml"
CONTRACT="contracts/evolution/STH-COMMUNITY-ONBOARDING-v1.0.yaml"
PIPELINE="registries/evolution/m10-004-progressive-build-pipeline-v1.0.yaml"
BASELINE="certification-evidence/m10-001/san-tan-heights-production-baseline-v1.0.0.json"


def registry():
    return load_hardening_registry(REGISTRY)


def profile():
    return load_pilot_profile(PROFILE)


def baseline_fp():
    return sha256(Path(BASELINE).read_bytes()).hexdigest()


def replay(p=None,r=None):
    return execute_hardened_replay(
        repository_root=".",
        original_profile=p or profile(),
        hardening_registry=r or registry(),
        onboarding_contract_path=CONTRACT,
        pipeline_registry_path=PIPELINE,
        san_tan_baseline_path=BASELINE,
        expected_san_tan_baseline_fingerprint=baseline_fp(),
    )


def test_all_four_m10_005_friction_items_have_explicit_disposition():
    rows=registry()["dispositions"]
    assert {x["work_item_id"] for x in rows}=={"COM-001","SRC-001","SRC-002","SRC-003"}
    assert all(x["disposition"]=="GOVERNED_PROFILE_INPUT" for x in rows)
    assert all(x["post_action"]=="CONFIGURE" for x in rows)


def test_hardening_preserves_original_component_classifications():
    result=replay()
    assert result.retained_classifications=={
        "COM-001":"COMMUNITY_SPECIFIC",
        "SRC-001":"SOURCE_SPECIFIC",
        "SRC-002":"SOURCE_SPECIFIC",
        "SRC-003":"SOURCE_SPECIFIC",
    }


def test_hardened_profiles_exist_validate_and_are_deterministic():
    a=validate_disposition_artifacts(repository_root=".",registry=registry())
    b=validate_disposition_artifacts(repository_root=".",registry=registry())
    assert set(a)=={"COM-001","SRC-001","SRC-002","SRC-003"}
    assert {k:v.fingerprint for k,v in a.items()}=={k:v.fingerprint for k,v in b.items()}


def test_listing_profile_does_not_imply_mls_access():
    p=load_governed_profile(
        "config/hardening/rancho_vistoso/mlssaz-compatibility-profile-v1.0.yaml",
        registry=registry(),
    )
    assert p.payload["access_policy"]["proprietary_records_used"] is False
    assert p.payload["access_policy"]["credentials_available"] is False


def test_rancho_vistoso_replay_reduces_manual_remediation_from_four_to_zero():
    result=replay()
    assert result.status=="PASS"
    assert result.prior_manual_remediation==4
    assert result.post_manual_remediation==0
    assert result.reduction==4
    assert result.prior_remediation_fraction=="4/11"
    assert result.post_remediation_fraction=="0/11"
    assert len(result.progressive_candidate_fingerprint)==64
    assert len(result.replay_fingerprint)==64


def test_replay_is_deterministic():
    a=replay()
    b=replay()
    assert a.replay_fingerprint==b.replay_fingerprint
    assert a.profile_fingerprints==b.profile_fingerprints
    assert a.progressive_candidate_fingerprint==b.progressive_candidate_fingerprint


def test_disposition_ledger_must_exactly_cover_prior_remediation():
    r=deepcopy(registry())
    r["dispositions"]=r["dispositions"][:-1]
    with pytest.raises(ValueError,match="exactly cover"):
        replay(r=r)


def test_classification_drift_fails_closed():
    r=deepcopy(registry())
    r["dispositions"][0]["prior_class"]="CORE_REUSABLE"
    with pytest.raises(ValueError,match="classification"):
        replay(r=r)


def test_missing_hardened_profile_fails_closed():
    r=deepcopy(registry())
    r["dispositions"][0]["hardened_artifact"]="config/hardening/rancho_vistoso/missing.yaml"
    with pytest.raises(ValueError,match="missing hardened profile"):
        replay(r=r)


def test_san_tan_baseline_mutation_is_detected(tmp_path):
    raw=Path(BASELINE).read_bytes()
    p=tmp_path/"baseline.json"
    p.write_bytes(raw+b" ")
    with pytest.raises(ValueError,match="accepted parent baseline changed"):
        execute_hardened_replay(
            repository_root=".",
            original_profile=profile(),
            hardening_registry=registry(),
            onboarding_contract_path=CONTRACT,
            pipeline_registry_path=PIPELINE,
            san_tan_baseline_path=p,
            expected_san_tan_baseline_fingerprint=baseline_fp(),
        )
