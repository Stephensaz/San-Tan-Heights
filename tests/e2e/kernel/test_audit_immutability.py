from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
def test_audit_tables_have_immutable_update_delete_triggers():
 sql=(ROOT/'database/migrations/0121_immutability_triggers.sql').read_text()
 for table in ('orchestration_events','state_transitions','guard_evaluations'):
  assert table in sql
 assert sql.count('BEFORE UPDATE OR DELETE') >= 3
