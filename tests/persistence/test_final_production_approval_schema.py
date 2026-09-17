from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SQL=(ROOT/'database/migrations/0095_final_production_approval.sql').read_text()

def test_final_approval_tables_exist():
    for name in ('rollback_containment_runs','rollback_containment_items','production_evidence_bundles','production_evidence_bundle_items','production_certification_revocations','full_approvals'):
        assert f'certification.{name}' in SQL

def test_final_approval_evidence_is_immutable():
    for name in ('trg_rollback_containment_runs_immutable','trg_rollback_containment_items_immutable','trg_production_evidence_bundles_immutable','trg_production_evidence_bundle_items_immutable','trg_production_certification_revocations_immutable','trg_full_approvals_immutable'):
        assert name in SQL
    assert SQL.count('shared.raise_immutable_row()') >= 6
