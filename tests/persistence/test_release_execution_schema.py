from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def test_release_execution_migration_contains_audit_validation_and_approval_evidence():
    sql=(ROOT/'database/migrations/0082_release_execution_control.sql').read_text()
    for needle in ['release_item_history','release_validation_results','release_approvals','release_items_item_state_check']:
        assert needle in sql
    assert "'PUBLISHED'" in sql and "'ROLLED_BACK'" in sql and "'CANCELLED'" in sql
