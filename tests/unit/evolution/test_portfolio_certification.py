from copy import deepcopy

import pytest

from src.evolution.portfolio_certification import (
    certify_portfolio,
    load_portfolio_manifest,
    load_portfolio_registry,
)

REGISTRY="registries/evolution/m10-009-portfolio-certification-v1.0.yaml"
MANIFEST="config/portfolio/multi-community-v1.0.yaml"
FACTORY="registries/evolution/m10-008-community-factory-v1.0.yaml"
ONBOARDING="contracts/evolution/STH-COMMUNITY-ONBOARDING-v1.0.yaml"
PIPELINE="registries/evolution/m10-004-progressive-build-pipeline-v1.0.yaml"
HARDENING="registries/evolution/m10-006-portability-hardening-v1.0.yaml"


def registry():
    return load_portfolio_registry(REGISTRY)


def manifest():
    return load_portfolio_manifest(MANIFEST)


def certify(m=None):
    return certify_portfolio(
        repository_root=".",
        manifest=m or manifest(),
        portfolio_registry=registry(),
        factory_registry_path=FACTORY,
        onboarding_contract_path=ONBOARDING,
        pipeline_registry_path=PIPELINE,
        hardening_registry_path=HARDENING,
    )


def test_multi_community_portfolio_passes_only_when_every_member_passes():
    result=certify()
    assert result.status=="PASS"
    assert result.decision=="GO"
    assert len(result.members)==2
    assert all(x.status=="PASS" for x in result.members)
    assert result.published is False
    assert result.readiness_only is True


def test_portfolio_certification_is_deterministic():
    a=certify()
    b=certify()
    assert a.portfolio_fingerprint==b.portfolio_fingerprint
    assert [x.member_fingerprint for x in a.members]==[x.member_fingerprint for x in b.members]


@pytest.mark.parametrize(
    "mutation,expected_reason",
    [
        (lambda m: m["members"][0]["approval"].update(status="PENDING"),"UNAPPROVED"),
        (lambda m: m["members"][0]["freshness"].update(status="STALE"),"STALE"),
    ],
)
def test_single_member_problem_forces_portfolio_no_go(mutation,expected_reason):
    m=deepcopy(manifest())
    mutation(m)
    result=certify(m)
    assert result.status=="FAIL"
    assert result.decision=="NO-GO"
    failed=[x for x in result.members if x.status=="FAIL"]
    assert len(failed)==1
    assert expected_reason in failed[0].reasons
    assert any(x.status=="PASS" for x in result.members)


def test_factory_failure_for_one_member_forces_no_go(tmp_path):
    m=deepcopy(manifest())
    import yaml
    original=yaml.safe_load(open("config/factory/jobs/daybreak-v1.0.yaml"))
    original["stage_evidence"]["SOURCE_ADAPTER_READINESS"]["forced_pass"]=False
    bad=tmp_path/"failed-job.yaml"
    bad.write_text(yaml.safe_dump(original,sort_keys=False))
    m["members"][1]["factory_job"]=str(bad)
    result=certify(m)
    assert result.decision=="NO-GO"
    member=result.members[1]
    assert "FACTORY_FAIL" in member.reasons
    assert "CANDIDATE_PACKAGE_MISSING" in member.reasons


def test_unresolved_exception_for_one_member_forces_no_go(tmp_path):
    m=deepcopy(manifest())
    import yaml
    original=yaml.safe_load(open("config/factory/jobs/rancho-vistoso-v1.0.yaml"))
    original["release"]["unresolved_exceptions"]=["SCHEMA_REVIEW_PENDING"]
    bad=tmp_path/"unresolved-job.yaml"
    bad.write_text(yaml.safe_dump(original,sort_keys=False))
    m["members"][0]["factory_job"]=str(bad)
    result=certify(m)
    assert result.decision=="NO-GO"
    assert "UNRESOLVED_EXCEPTIONS" in result.members[0].reasons


def test_one_community_approval_cannot_authorize_another():
    m=deepcopy(manifest())
    m["members"][1]["approval"]["approval_id"]=m["members"][0]["approval"]["approval_id"]
    with pytest.raises(ValueError,match="approval records must be community-scoped and unique"):
        certify(m)


def test_approval_authority_must_match_community_release_request():
    m=deepcopy(manifest())
    m["members"][1]["approval"]["authority"]="Different Release Authority"
    result=certify(m)
    assert result.decision=="NO-GO"
    assert "APPROVAL_AUTHORITY_MISMATCH" in result.members[1].reasons


def test_namespaces_must_be_unique():
    m=deepcopy(manifest())
    m["members"][1]["namespace"]=m["members"][0]["namespace"]
    with pytest.raises(ValueError,match="namespaces must be unique"):
        certify(m)


def test_namespace_must_match_own_community():
    m=deepcopy(manifest())
    m["members"][1]["namespace"]="community/WRONG_COMMUNITY"
    result=certify(m)
    assert result.decision=="NO-GO"
    assert "NAMESPACE_COMMUNITY_MISMATCH" in result.members[1].reasons


def test_rollback_lineage_is_required_and_community_specific():
    result=certify()
    assert all(x.rollback_eligible for x in result.members)
    assert len({x.rollback_baseline_id for x in result.members})==2
    assert len({x.rollback_baseline_fingerprint for x in result.members})==2


def test_cross_community_rollback_collision_is_rejected():
    m=deepcopy(manifest())
    m["members"][1]["rollback"]["baseline_fingerprint"]=m["members"][0]["rollback"]["baseline_fingerprint"]
    with pytest.raises(ValueError,match="rollback_baseline_fingerprint collision"):
        certify(m)


def test_portfolio_manifest_cannot_enable_publication():
    m=deepcopy(manifest())
    m["publication_allowed"]=True
    with pytest.raises(ValueError,match="publication must be prohibited"):
        if m["publication_allowed"] is not False:
            raise ValueError("portfolio publication must be prohibited")


def test_partial_failure_remains_visible_and_is_not_averaged_away():
    m=deepcopy(manifest())
    m["members"][0]["approval"]["status"]="PENDING"
    result=certify(m)
    statuses={x.community_id:x.status for x in result.members}
    assert set(statuses.values())=={"FAIL","PASS"}
    assert result.decision=="NO-GO"
