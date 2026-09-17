from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SQL=(ROOT/'database/migrations/0094_publication_automation_baselines.sql').read_text()

def test_automation_handoff_and_baseline_tables_present():
    assert 'certification.automation_handoffs' in SQL
    assert 'certification.rollback_baselines' in SQL
    assert 'certification.rollback_baseline_entries' in SQL

def test_baseline_evidence_is_immutable():
    assert 'trg_automation_handoffs_immutable' in SQL
    assert 'trg_rollback_baselines_immutable' in SQL
    assert 'trg_rollback_baseline_entries_immutable' in SQL
    assert SQL.count('shared.raise_immutable_row()') >= 3
