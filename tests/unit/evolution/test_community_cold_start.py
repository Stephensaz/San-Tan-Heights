from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from src.evolution.community_cold_start import (
    execute_cold_start,
    load_cold_start_profile,
)

PROFILE="config/cold_start/daybreak/cold-start-v1.0.yaml"
CONTRACT="contracts/evolution/STH-COMMUNITY-ONBOARDING-v1.0.yaml"
PIPELINE="registries/evolution/m10-004-progressive-build-pipeline-v1.0.yaml"
HARDENING="registries/evolution/m10-006-portability-hardening-v1.0.yaml"


def profile():
    return load_cold_start_profile(PROFILE)


def execute(p=None):
    return execute_cold_start(
        repository_root=".",
        profile=p or profile(),
        onboarding_contract_path=CONTRACT,
        pipeline_registry_path=PIPELINE,
        hardening_registry_path=HARDENING,
    )


def test_daybreak_is_real_materially_distinct_clean_start():
    p=profile()
    assert p["community"]["community_id"]=="DAYBREAK_UT"
    assert p["community"]["state"]=="UT"
    assert p["community"]["county"]=="Salt Lake"
    assert p["community"]["municipality"]=="South Jordan"
    assert "UtahRealEstate" in p["source_systems"]["listing_service"]
    assert p["cold_start_policy"]["prior_pilot_artifacts_allowed"] is False


def test_cold_start_uses_exact_four_governed_profile_types():
    result=execute()
    assert set(result.profile_fingerprints)=={
        "COMMUNITY_TAXONOMY",
        "LISTING_SOURCE_COMPATIBILITY",
        "PARCEL_SOURCE_COMPATIBILITY",
        "RECORDER_SOURCE_COMPATIBILITY",
    }


def test_clean_start_passes_with_zero_manual_remediation():
    result=execute()
    assert result.status=="PASS"
    assert result.metrics.total_work_items==11
    assert result.metrics.reuse_unchanged==4
    assert result.metrics.configured==7
    assert result.metrics.remediated==0
    assert result.metrics.counts_by_class=={
        "COMMUNITY_CONFIGURABLE":3,
        "COMMUNITY_SPECIFIC":1,
        "CORE_REUSABLE":4,
        "SOURCE_SPECIFIC":3,
    }
    assert result.blocking_exceptions==()


def test_repeatability_is_deterministic():
    a=execute()
    b=execute()
    assert a.repeatability_fingerprint==b.repeatability_fingerprint
    assert a.bootstrap_fingerprint==b.bootstrap_fingerprint
    assert a.progressive_candidate_fingerprint==b.progressive_candidate_fingerprint
    assert a.profile_fingerprints==b.profile_fingerprints


def test_comparison_proves_hardening_repeatability():
    result=execute()
    assert result.comparison=={
        "pre_hardening":"4/11",
        "post_hardening":"0/11",
        "third_community_cold_start":"0/11",
    }


def test_no_prior_pilot_specific_artifacts_are_referenced():
    p=profile()
    raw=yaml.safe_dump(p,sort_keys=True)
    assert "RANCHO_VISTOSO" not in raw
    assert "rancho_vistoso" not in raw
    result=execute()
    assert result.metrics.prior_pilot_dependencies==()


def test_injecting_prior_pilot_dependency_fails_closed():
    p=deepcopy(profile())
    p["governed_profiles"][0]="config/hardening/rancho_vistoso/community-taxonomy-profile-v1.0.yaml"
    with pytest.raises(ValueError,match="prior-pilot artifact dependency prohibited"):
        execute(p)


def test_missing_governed_profile_fails_closed():
    p=deepcopy(profile())
    p["governed_profiles"]=p["governed_profiles"][:-1]
    with pytest.raises(ValueError,match="exactly one governed profile"):
        execute(p)


def test_governed_profile_community_mismatch_fails_closed(tmp_path):
    p=deepcopy(profile())
    raw=yaml.safe_load(Path(p["governed_profiles"][0]).read_text())
    raw["community_id"]="OTHER_COMMUNITY"
    bad=tmp_path/"bad-profile.yaml"
    bad.write_text(yaml.safe_dump(raw,sort_keys=False))
    p["governed_profiles"][0]=str(bad)
    with pytest.raises(ValueError,match="community mismatch"):
        execute(p)


def test_manual_remediation_action_is_prohibited():
    p=deepcopy(profile())
    p["work_items"][-1]["action"]="REMEDIATE"
    with pytest.raises(ValueError,match="requires manual remediation"):
        execute(p)


def test_proprietary_mls_access_cannot_be_enabled(tmp_path):
    p=deepcopy(profile())
    listing=Path("config/cold_start/daybreak/utahrealestate-compatibility-profile-v1.0.yaml")
    raw=yaml.safe_load(listing.read_text())
    raw["access_policy"]["proprietary_records_used"]=True
    bad=tmp_path/"bad-listing.yaml"
    bad.write_text(yaml.safe_dump(raw,sort_keys=False))
    p["governed_profiles"][1]=str(bad)
    with pytest.raises(ValueError,match="may not imply proprietary record access"):
        execute(p)


def test_source_provenance_is_required():
    p=deepcopy(profile())
    del p["source_provenance"]["recorder_authority"]
    with pytest.raises(ValueError,match="source provenance incomplete"):
        execute(p)
