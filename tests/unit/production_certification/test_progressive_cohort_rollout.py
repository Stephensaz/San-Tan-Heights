from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from src.production_certification.cohort.certification import CohortEvidenceCertification
from src.production_certification.cohort.membership import FrozenCohortMembership
from src.production_certification.cohort.progressive import (
    ProgressiveCohortDeploymentService,
    ProgressiveCohortEvidenceCertifier,
    ProgressiveCohortMembershipFreezer,
    ProgressiveRolloutPolicy,
)
from src.production_certification.go_live.stop_conditions import GoLiveStopResult

NOW = datetime(2026, 9, 16, 23, 0, tzinfo=timezone.utc)
PC = UUID(int=9000)
CANDIDATE = "c" * 64
FLEET_FP = "f" * 64


def initial_25():
    props = tuple(UUID(int=i + 1) for i in range(25))
    membership = FrozenCohortMembership(
        UUID(int=7001), PC, "COHORT_25", "1.0.0", CANDIDATE, "p" * 64,
        UUID(int=7002), "a" * 64, props, ("AGENT", "SELLER", "PUBLIC"), "m" * 64,
        "ops", NOW,
    )
    cert = CohortEvidenceCertification(
        UUID(int=7003), PC, membership.cohort_id, UUID(int=7004), "1.0.0", "PASS", (), 25, 25, 25,
        membership.membership_fingerprint, "d" * 64, "e" * 64, "certifier",
    )
    return membership, cert


class Executor:
    def __init__(self, fail_on=None): self.fail_on = fail_on; self.calls = []
    def deploy(self, *, property_id, variants, candidate_fingerprint):
        self.calls.append(property_id)
        if property_id == self.fail_on: raise RuntimeError("activation failed")
        return {"variants": list(variants), "candidate_fingerprint": candidate_fingerprint}


def stop():
    return GoLiveStopResult(PC, "1.0.0", "CLEAR", (), "s" * 64, "ops")


def fleet(n=4956):
    return tuple(UUID(int=i + 1) for i in range(n))


def test_progressive_registry_has_100_500_and_remaining():
    p = ProgressiveRolloutPolicy.load("registries/production-certification/progressive-rollout-policy.yaml")
    assert p.require_stage("COHORT_100").property_count == 100
    assert p.require_stage("COHORT_500").property_count == 500
    assert p.require_stage("REMAINING_FLEET").property_count is None


def test_cohort_100_excludes_certified_25_and_freezes_next_100():
    policy = ProgressiveRolloutPolicy.load("registries/production-certification/progressive-rollout-policy.yaml")
    m25, c25 = initial_25()
    m100 = ProgressiveCohortMembershipFreezer().freeze(
        policy=policy, cohort_code="COHORT_100", production_certification_id=PC,
        candidate_fingerprint=CANDIDATE, fleet_eligibility_fingerprint=FLEET_FP,
        eligible_property_ids=fleet(), prior_memberships=(m25,), prior_certification=c25,
        current_stop_conditions=stop(), frozen_by="ops", frozen_at=NOW,
    )
    assert len(m100.property_ids) == 100
    assert not set(m100.property_ids).intersection(m25.property_ids)
    assert m100.property_ids[0] == UUID(int=26)


def test_progressive_chain_reaches_remaining_fleet_without_overlap():
    policy = ProgressiveRolloutPolicy.load("registries/production-certification/progressive-rollout-policy.yaml")
    freezer = ProgressiveCohortMembershipFreezer(); deployer = ProgressiveCohortDeploymentService(); certifier = ProgressiveCohortEvidenceCertifier()
    m25, c25 = initial_25()
    m100 = freezer.freeze(policy=policy, cohort_code="COHORT_100", production_certification_id=PC,
        candidate_fingerprint=CANDIDATE, fleet_eligibility_fingerprint=FLEET_FP, eligible_property_ids=fleet(),
        prior_memberships=(m25,), prior_certification=c25, current_stop_conditions=stop(), frozen_by="ops", frozen_at=NOW)
    d100 = deployer.deploy(membership=m100, prior_certification=c25, current_stop_conditions=stop(), executor=Executor(), deployed_by="ops", started_at=NOW)
    c100 = certifier.certify(membership=m100, deployment=d100, certified_by="certifier")
    assert c100.certification_status == "PASS" and len(m100.property_ids) == 100

    m500 = freezer.freeze(policy=policy, cohort_code="COHORT_500", production_certification_id=PC,
        candidate_fingerprint=CANDIDATE, fleet_eligibility_fingerprint=FLEET_FP, eligible_property_ids=fleet(),
        prior_memberships=(m25,m100), prior_certification=c100, current_stop_conditions=stop(), frozen_by="ops", frozen_at=NOW)
    d500 = deployer.deploy(membership=m500, prior_certification=c100, current_stop_conditions=stop(), executor=Executor(), deployed_by="ops", started_at=NOW)
    c500 = certifier.certify(membership=m500, deployment=d500, certified_by="certifier")
    assert c500.certification_status == "PASS" and len(m500.property_ids) == 500

    remaining = freezer.freeze(policy=policy, cohort_code="REMAINING_FLEET", production_certification_id=PC,
        candidate_fingerprint=CANDIDATE, fleet_eligibility_fingerprint=FLEET_FP, eligible_property_ids=fleet(),
        prior_memberships=(m25,m100,m500), prior_certification=c500, current_stop_conditions=stop(), frozen_by="ops", frozen_at=NOW)
    assert len(remaining.property_ids) == 4956 - 25 - 100 - 500
    sets = [set(x.property_ids) for x in (m25,m100,m500,remaining)]
    assert sum(len(x) for x in sets) == len(set().union(*sets)) == 4956


def test_progressive_deployment_is_fail_fast():
    policy = ProgressiveRolloutPolicy.load("registries/production-certification/progressive-rollout-policy.yaml")
    m25, c25 = initial_25()
    m100 = ProgressiveCohortMembershipFreezer().freeze(policy=policy, cohort_code="COHORT_100",
        production_certification_id=PC, candidate_fingerprint=CANDIDATE, fleet_eligibility_fingerprint=FLEET_FP,
        eligible_property_ids=fleet(), prior_memberships=(m25,), prior_certification=c25,
        current_stop_conditions=stop(), frozen_by="ops", frozen_at=NOW)
    failed = m100.property_ids[9]; ex = Executor(fail_on=failed)
    d = ProgressiveCohortDeploymentService().deploy(membership=m100, prior_certification=c25,
        current_stop_conditions=stop(), executor=ex, deployed_by="ops", started_at=NOW)
    assert d.deployment_status == "FAIL" and len(d.items) == 10
    assert m100.property_ids[10] not in ex.calls


def test_next_stage_requires_pass_certification_of_immediate_prior_cohort():
    policy = ProgressiveRolloutPolicy.load("registries/production-certification/progressive-rollout-policy.yaml")
    m25, c25 = initial_25()
    m100 = ProgressiveCohortMembershipFreezer().freeze(policy=policy, cohort_code="COHORT_100",
        production_certification_id=PC, candidate_fingerprint=CANDIDATE, fleet_eligibility_fingerprint=FLEET_FP,
        eligible_property_ids=fleet(), prior_memberships=(m25,), prior_certification=c25,
        current_stop_conditions=stop(), frozen_by="ops", frozen_at=NOW)
    bad = CohortEvidenceCertification(UUID(int=8), PC, m25.cohort_id, UUID(int=9), "1.0.0", "FAIL", ("X",), 25, 7, 6,
        m25.membership_fingerprint, "d"*64, "e"*64, "certifier")
    with pytest.raises(ValueError, match="has not passed"):
        ProgressiveCohortMembershipFreezer().freeze(policy=policy, cohort_code="COHORT_500",
            production_certification_id=PC, candidate_fingerprint=CANDIDATE, fleet_eligibility_fingerprint=FLEET_FP,
            eligible_property_ids=fleet(), prior_memberships=(m25,m100), prior_certification=bad,
            current_stop_conditions=stop(), frozen_by="ops", frozen_at=NOW)
