from __future__ import annotations
import json
from .models import ProductionCertificationRun, ProductionEvidence, ProductionCheckResult


class ProductionCertificationRepository:
    CREATE_RUN = '''INSERT INTO certification.production_runs
(production_certification_id,system_certification_run_id,contract_version,candidate_version,candidate_fingerprint,run_state,verdict,correlation_id,created_by)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)'''

    APPEND_EVIDENCE = '''INSERT INTO certification.production_evidence
(production_evidence_id,production_certification_id,evidence_type,subject_key,evidence_hash,evidence_payload,source_uri,captured_by)
VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s)'''

    APPEND_CHECK = '''INSERT INTO certification.production_check_results
(production_check_result_id,production_certification_id,stage_code,check_code,status,evidence_hash,detail,observed_by)
VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s)'''

    GET_RUN = '''SELECT production_certification_id,system_certification_run_id,contract_version,candidate_version,candidate_fingerprint,run_state,verdict,correlation_id,created_by,started_at,completed_at,created_at,updated_at
FROM certification.production_runs WHERE production_certification_id=%s'''

    def create_run(self, cursor, run: ProductionCertificationRun) -> None:
        cursor.execute(self.CREATE_RUN, (
            run.production_certification_id, run.system_certification_run_id,
            run.contract_version, run.candidate_version, run.candidate_fingerprint,
            run.run_state, run.verdict, run.correlation_id, run.created_by,
        ))

    def append_evidence(self, cursor, evidence: ProductionEvidence) -> None:
        cursor.execute(self.APPEND_EVIDENCE, (
            evidence.production_evidence_id, evidence.production_certification_id,
            evidence.evidence_type, evidence.subject_key, evidence.evidence_hash,
            json.dumps(dict(evidence.evidence_payload), sort_keys=True, separators=(',', ':')),
            evidence.source_uri, evidence.captured_by,
        ))

    def append_check_result(self, cursor, result: ProductionCheckResult) -> None:
        cursor.execute(self.APPEND_CHECK, (
            result.production_check_result_id, result.production_certification_id,
            result.stage_code, result.check_code, result.status, result.evidence_hash,
            json.dumps(dict(result.detail), sort_keys=True, separators=(',', ':')),
            result.observed_by,
        ))

    def get_run(self, cursor, production_certification_id):
        cursor.execute(self.GET_RUN, (production_certification_id,))
        return cursor.fetchone()

    INSERT_CANDIDATE_FREEZE = '''INSERT INTO certification.production_candidate_freezes
(production_certification_id,candidate_version,candidate_fingerprint,artifact_sha256,source_revision,artifact_uri,freeze_fingerprint,frozen_by)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s)'''

    INSERT_MANIFEST_PIN = '''INSERT INTO certification.production_manifest_pins
(production_certification_id,manifest_type,manifest_version,manifest_sha256,manifest_payload,pin_fingerprint,pinned_by)
VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s)'''

    INSERT_ENVIRONMENT_PARITY = '''INSERT INTO certification.production_environment_parity
(production_certification_id,policy_version,expected_fingerprint,observed_fingerprint,parity_status,mismatch_keys,expected_environment,observed_environment,verifier_version,verified_by)
VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s)'''

    def insert_candidate_freeze(self, cursor, freeze) -> None:
        cursor.execute(self.INSERT_CANDIDATE_FREEZE, (
            freeze.production_certification_id, freeze.candidate_version,
            freeze.candidate_fingerprint, freeze.artifact_sha256,
            freeze.source_revision, freeze.artifact_uri,
            freeze.freeze_fingerprint, freeze.frozen_by,
        ))

    def insert_manifest_pin(self, cursor, pin) -> None:
        cursor.execute(self.INSERT_MANIFEST_PIN, (
            pin.production_certification_id, pin.manifest_type, pin.manifest_version,
            pin.manifest_sha256,
            json.dumps(dict(pin.manifest_payload), sort_keys=True, separators=(',', ':')),
            pin.pin_fingerprint, pin.pinned_by,
        ))

    def insert_environment_parity(self, cursor, result) -> None:
        cursor.execute(self.INSERT_ENVIRONMENT_PARITY, (
            result.production_certification_id, result.policy_version,
            result.expected_fingerprint, result.observed_fingerprint,
            result.parity_status,
            json.dumps(list(result.mismatch_keys), separators=(',', ':')),
            json.dumps(dict(result.expected_environment), sort_keys=True, separators=(',', ':')),
            json.dumps(dict(result.observed_environment), sort_keys=True, separators=(',', ':')),
            result.verifier_version, result.verified_by,
        ))

    INSERT_CONFIGURATION_VALIDATION = """INSERT INTO certification.production_configuration_validations
(production_certification_id,policy_version,configuration_fingerprint,validation_status,violation_codes,observed_configuration,validator_version,validated_by)
VALUES (%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s)"""

    INSERT_PILOT_MEMBERSHIP = """INSERT INTO certification.production_pilot_memberships
(production_certification_id,policy_version,membership_fingerprint,selected_count,selected_property_ids,decision_evidence,resolved_by)
VALUES (%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s)"""

    def insert_configuration_validation(self, cursor, result) -> None:
        cursor.execute(self.INSERT_CONFIGURATION_VALIDATION, (
            result.production_certification_id, result.policy_version,
            result.configuration_fingerprint, result.status,
            json.dumps(list(result.violation_codes), separators=(',', ':')),
            json.dumps(dict(result.observed_configuration), sort_keys=True, separators=(',', ':')),
            result.validator_version, result.validated_by,
        ))

    def insert_pilot_membership(self, cursor, *, production_certification_id, result, resolved_by: str) -> None:
        decisions=[{
            'property_id':str(x.property_id),'eligible':x.eligible,
            'reason_codes':list(x.reason_codes),'snapshot_id':str(x.snapshot_id) if x.snapshot_id else None,
        } for x in result.decisions]
        cursor.execute(self.INSERT_PILOT_MEMBERSHIP, (
            production_certification_id, result.policy_version, result.membership_fingerprint,
            len(result.selected_property_ids),
            json.dumps([str(x) for x in result.selected_property_ids], separators=(',', ':')),
            json.dumps(decisions, sort_keys=True, separators=(',', ':')),
            resolved_by,
        ))


# M7-008 through M7-010 persistence helpers. Kept outside the core run/evidence methods
# so production-certification lifecycle semantics remain explicit and reviewable.
def _insert_shadow_cycle(self, cursor, cycle) -> None:
    cursor.execute('''INSERT INTO certification.production_shadow_cycles
(shadow_cycle_id,production_certification_id,cycle_number,policy_version,pilot_membership_fingerprint,target_count,passed_target_count,failed_target_count,cycle_status,orchestrator_evidence_hash,cycle_fingerprint,recorded_by)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''', (
        cycle.shadow_cycle_id, cycle.production_certification_id, cycle.cycle_number,
        cycle.policy_version, cycle.pilot_membership_fingerprint, cycle.target_count,
        cycle.passed_target_count, cycle.failed_target_count, cycle.cycle_status,
        cycle.orchestrator_evidence_hash, cycle.cycle_fingerprint, cycle.recorded_by,
    ))
    for target in cycle.target_results:
        cursor.execute('''INSERT INTO certification.production_shadow_cycle_targets
(shadow_cycle_id,property_id,report_variant,target_status,generated_fingerprint,comparison_fingerprint,detail,target_evidence_hash)
VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s)''', (
            cycle.shadow_cycle_id,target.property_id,target.variant,target.status,
            target.generated_fingerprint,target.comparison_fingerprint,
            json.dumps(dict(target.detail),sort_keys=True,separators=(',',':')),
            target.target_evidence_hash,
        ))


def _insert_manual_audit_sample(self, cursor, sample) -> None:
    cursor.execute('''INSERT INTO certification.production_manual_audit_samples
(manual_audit_sample_id,production_certification_id,shadow_cycle_id,policy_version,sample_size,sampled_property_ids,failed_shadow_property_ids,sample_fingerprint,built_by)
VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s)''', (
        sample.manual_audit_sample_id,sample.production_certification_id,sample.shadow_cycle_id,
        sample.policy_version,len(sample.sampled_property_ids),
        json.dumps([str(x) for x in sample.sampled_property_ids],separators=(',',':')),
        json.dumps([str(x) for x in sample.failed_shadow_property_ids],separators=(',',':')),
        sample.sample_fingerprint,sample.built_by,
    ))


def _insert_manual_audit_evidence(self, cursor, evidence) -> None:
    cursor.execute('''INSERT INTO certification.production_manual_audit_evidence
(manual_audit_evidence_id,manual_audit_sample_id,property_id,audit_status,checklist_version,checklist_results,notes,evidence_hash,reviewed_by)
VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s)''', (
        evidence.manual_audit_evidence_id,evidence.manual_audit_sample_id,evidence.property_id,
        evidence.audit_status,evidence.checklist_version,
        json.dumps(dict(evidence.checklist_results),sort_keys=True,separators=(',',':')),
        evidence.notes,evidence.evidence_hash,evidence.reviewed_by,
    ))

ProductionCertificationRepository.insert_shadow_cycle = _insert_shadow_cycle
ProductionCertificationRepository.insert_manual_audit_sample = _insert_manual_audit_sample
ProductionCertificationRepository.insert_manual_audit_evidence = _insert_manual_audit_evidence

def _insert_shadow_acceptance(self, cursor, result) -> None:
    cursor.execute('''INSERT INTO certification.production_shadow_acceptance
(production_certification_id,policy_version,acceptance_status,reason_codes,accepted_cycle_ids,latest_shadow_cycle_id,manual_audit_sample_id,acceptance_fingerprint,evaluated_by)
VALUES (%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s,%s)''', (
        result.production_certification_id,result.policy_version,result.status,
        json.dumps(list(result.reason_codes),separators=(',',':')),
        json.dumps([str(x) for x in result.accepted_cycle_ids],separators=(',',':')),
        result.latest_shadow_cycle_id,result.manual_audit_sample_id,result.acceptance_fingerprint,result.evaluated_by))

def _insert_go_live_stop_result(self, cursor, result) -> None:
    cursor.execute('''INSERT INTO certification.production_go_live_stop_results
(production_certification_id,policy_version,stop_status,blocking_conditions,evidence_fingerprint,evaluated_by)
VALUES (%s,%s,%s,%s::jsonb,%s,%s)''', (result.production_certification_id,result.policy_version,result.status,
        json.dumps(list(result.blocking_conditions),separators=(',',':')),result.evidence_fingerprint,result.evaluated_by))

def _insert_limited_approval(self, cursor, approval) -> None:
    cursor.execute('''INSERT INTO certification.production_limited_approvals
(limited_approval_id,production_certification_id,policy_version,approval_type,candidate_fingerprint,pilot_membership_fingerprint,max_properties,allowed_variants,shadow_acceptance_fingerprint,stop_condition_fingerprint,issued_at,expires_at,approval_fingerprint,approved_by)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s)''', (approval.limited_approval_id,approval.production_certification_id,
        approval.policy_version,approval.approval_type,approval.candidate_fingerprint,approval.pilot_membership_fingerprint,approval.max_properties,
        json.dumps(list(approval.allowed_variants),separators=(',',':')),approval.shadow_acceptance_fingerprint,approval.stop_condition_fingerprint,
        approval.issued_at,approval.expires_at,approval.approval_fingerprint,approval.approved_by))

ProductionCertificationRepository.insert_shadow_acceptance = _insert_shadow_acceptance
ProductionCertificationRepository.insert_go_live_stop_result = _insert_go_live_stop_result
ProductionCertificationRepository.insert_limited_approval = _insert_limited_approval

# M7-014 through M7-016 cohort rollout persistence helpers.
def _insert_cohort_membership(self, cursor, membership) -> None:
    cursor.execute('''INSERT INTO certification.production_cohorts
(cohort_id,production_certification_id,cohort_code,policy_version,candidate_fingerprint,pilot_membership_fingerprint,limited_approval_id,limited_approval_fingerprint,property_count,allowed_variants,membership_fingerprint,frozen_by,frozen_at)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s)''', (
        membership.cohort_id,membership.production_certification_id,membership.cohort_code,membership.policy_version,
        membership.candidate_fingerprint,membership.pilot_membership_fingerprint,membership.limited_approval_id,
        membership.limited_approval_fingerprint,len(membership.property_ids),
        json.dumps(list(membership.allowed_variants),separators=(',',':')),membership.membership_fingerprint,
        membership.frozen_by,membership.frozen_at,
    ))
    for ordinal, property_id in enumerate(membership.property_ids, start=1):
        cursor.execute('''INSERT INTO certification.production_cohort_members
(cohort_id,membership_ordinal,property_id) VALUES (%s,%s,%s)''', (membership.cohort_id,ordinal,property_id))


def _insert_cohort_deployment(self, cursor, deployment) -> None:
    cursor.execute('''INSERT INTO certification.production_cohort_deployments
(cohort_deployment_id,cohort_id,production_certification_id,candidate_fingerprint,limited_approval_fingerprint,membership_fingerprint,deployment_status,deployment_fingerprint,deployed_by,started_at,completed_at)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''', (
        deployment.cohort_deployment_id,deployment.cohort_id,deployment.production_certification_id,
        deployment.candidate_fingerprint,deployment.limited_approval_fingerprint,deployment.membership_fingerprint,
        deployment.deployment_status,deployment.deployment_fingerprint,deployment.deployed_by,
        deployment.started_at,deployment.completed_at,
    ))
    for item in deployment.items:
        cursor.execute('''INSERT INTO certification.production_cohort_deployment_items
(cohort_deployment_id,membership_ordinal,property_id,deployment_status,evidence_hash,detail)
VALUES (%s,%s,%s,%s,%s,%s::jsonb)''', (deployment.cohort_deployment_id,item.membership_ordinal,item.property_id,
            item.status,item.evidence_hash,json.dumps(dict(item.detail),sort_keys=True,separators=(',',':'))))


def _insert_cohort_certification(self, cursor, result) -> None:
    cursor.execute('''INSERT INTO certification.production_cohort_certifications
(cohort_certification_id,production_certification_id,cohort_id,cohort_deployment_id,policy_version,certification_status,reason_codes,expected_item_count,deployed_item_count,passed_item_count,membership_fingerprint,deployment_fingerprint,certification_fingerprint,certified_by)
VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s)''', (
        result.cohort_certification_id,result.production_certification_id,result.cohort_id,result.cohort_deployment_id,
        result.policy_version,result.certification_status,json.dumps(list(result.reason_codes),separators=(',',':')),
        result.expected_item_count,result.deployed_item_count,result.passed_item_count,result.membership_fingerprint,
        result.deployment_fingerprint,result.certification_fingerprint,result.certified_by,
    ))

ProductionCertificationRepository.insert_cohort_membership = _insert_cohort_membership
ProductionCertificationRepository.insert_cohort_deployment = _insert_cohort_deployment
ProductionCertificationRepository.insert_cohort_certification = _insert_cohort_certification
