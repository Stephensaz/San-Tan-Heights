from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def test_impact_migration_has_idempotency_and_reverse_lookup_index():
    s=(ROOT/'database/migrations/0192_report_impact_evaluations.sql').read_text()
    assert 'UNIQUE(source_event_id,property_id,report_variant,dependency_type,dependency_id)' in s
    assert 'idx_snapshot_dependency_reverse_lookup' in s
    assert "INVALIDATION_REQUIRED" in s

def test_dependency_events_and_reasons_are_seeded():
    events=(ROOT/'registries/events/events.yaml').read_text()
    reasons=(ROOT/'registries/reason-codes/reason-codes.yaml').read_text()
    seed=(ROOT/'database/migrations/0163_reference_seed_data.sql').read_text()
    for e in ['REPORT_IMPACT_EVALUATED','REPORT_MARKED_DIRTY','REPORT_BLOCKED_BY_DEPENDENCY','REPORT_INVALIDATION_RECOMMENDED','REPORT_REVIEW_REQUIRED']:
        assert e in events and e in seed
    for r in ['DEPENDENCY_SEMANTIC_CHANGE','INVALIDATING_CORRECTION','REQUIRED_DEPENDENCY_BLOCKED']:
        assert r in reasons and r in seed
