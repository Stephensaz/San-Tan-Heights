from copy import deepcopy
from pathlib import Path

import pytest

from src.evolution.portability_pilot import (
    execute_portability_pilot,
    load_pilot_profile,
    platform_fingerprint,
)

PROFILE = "config/pilots/rancho_vistoso/portability-pilot-v1.0.yaml"
CONTRACT = "contracts/evolution/STH-COMMUNITY-ONBOARDING-v1.0.yaml"
PIPELINE = "registries/evolution/m10-004-progressive-build-pipeline-v1.0.yaml"


def profile():
    return load_pilot_profile(PROFILE)


def execute(p=None):
    return execute_portability_pilot(
        repository_root=".",
        profile=p or profile(),
        onboarding_contract_path=CONTRACT,
        pipeline_registry_path=PIPELINE,
    )


def test_real_community_pilot_identity_and_data_boundary_are_explicit():
    p = profile()
    assert p["community"]["community_id"] == "RANCHO_VISTOSO"
    assert p["community"]["real_community"] is True
    assert p["community"]["county"] == "Pima"
    assert p["community"]["municipality"] == "Oro Valley"
    assert p["source_systems"]["listing_service"] == "MLSSAZ"
    assert p["pilot_data_policy"]["synthetic_property_corpus_only"] is True
    assert p["pilot_data_policy"]["proprietary_mls_records_used"] is False
    assert p["pilot_data_policy"]["homeowner_personal_data_used"] is False


def test_parent_platform_fingerprint_is_deterministic():
    assert platform_fingerprint(".") == platform_fingerprint(".")
    assert len(platform_fingerprint(".")) == 64


def test_rancho_vistoso_portability_pilot_passes_deterministically():
    a = execute()
    b = execute()
    assert a.status == "PASS"
    assert a.pilot_fingerprint == b.pilot_fingerprint
    assert a.bootstrap_fingerprint == b.bootstrap_fingerprint
    assert a.progressive_candidate_fingerprint == b.progressive_candidate_fingerprint
    assert a.unresolved_remediation == ()
    assert a.blocking_exceptions == ()


def test_metrics_measure_exact_classified_work_not_estimated_hours():
    result = execute()
    assert result.metrics.total_work_items == 11
    assert result.metrics.counts_by_class == {
        "COMMUNITY_CONFIGURABLE": 3,
        "COMMUNITY_SPECIFIC": 1,
        "CORE_REUSABLE": 4,
        "SOURCE_SPECIFIC": 3,
    }
    assert result.metrics.reuse_unchanged == 4
    assert result.metrics.configured == 3
    assert result.metrics.remediated == 4
    assert result.metrics.manual_remediation_items == ("COM-001", "SRC-001", "SRC-002", "SRC-003")
    assert result.metrics.reuse_fraction == "4/11"
    assert result.metrics.remediation_fraction == "4/11"


def test_every_remediate_work_item_requires_exact_ledger_coverage():
    p = deepcopy(profile())
    p["remediation"] = p["remediation"][:-1]
    with pytest.raises(ValueError, match="does not exactly cover"):
        execute(p)


def test_unresolved_manual_remediation_blocks_pilot():
    p = deepcopy(profile())
    p["remediation"][0]["status"] = "OPEN"
    with pytest.raises(ValueError, match="unresolved portability remediation"):
        execute(p)


def test_missing_real_source_provenance_blocks_pilot():
    p = deepcopy(profile())
    del p["source_provenance"]["parcel_authority"]
    with pytest.raises(ValueError, match="source provenance is incomplete"):
        execute(p)


def test_invalid_source_url_blocks_pilot():
    p = deepcopy(profile())
    p["source_provenance"]["listing_service"]["url"] = "not-a-url"
    with pytest.raises(ValueError, match="invalid source provenance"):
        execute(p)


def test_proprietary_mls_access_cannot_be_implied():
    p = deepcopy(profile())
    p["pilot_data_policy"]["proprietary_mls_records_used"] = True
    with pytest.raises(ValueError, match="must not imply proprietary MLS data access"):
        execute_portability_pilot(
            repository_root=".",
            profile=load_pilot_profile(PROFILE),
            onboarding_contract_path=CONTRACT,
            pipeline_registry_path=PIPELINE,
        )
    with pytest.raises(ValueError, match="must not imply proprietary MLS data access"):
        load_pilot_profile_from_mapping_for_test(p)


def load_pilot_profile_from_mapping_for_test(raw):
    tmp = Path("tests/unit/evolution/.tmp-m10-005-profile.yaml")
    import yaml
    tmp.write_text(yaml.safe_dump(raw, sort_keys=False))
    try:
        return load_pilot_profile(tmp)
    finally:
        tmp.unlink(missing_ok=True)


def test_missing_stage_evidence_blocks_progressive_execution():
    p = deepcopy(profile())
    del p["stage_evidence"]["EVIDENCE_PASSPORT_READINESS"]
    with pytest.raises(ValueError, match="missing pilot evidence"):
        execute(p)


def test_work_item_classification_must_be_governed():
    p = deepcopy(profile())
    p["work_items"][0]["component_class"] = "MYSTERY"
    with pytest.raises(ValueError, match="invalid component classification"):
        execute(p)


def test_pilot_profile_prohibits_publication():
    p = profile()
    assert p["pilot_data_policy"]["publication_allowed"] is False
