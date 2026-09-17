from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def test_publication_staging_schema_is_durable_and_target_unique():
    sql=(ROOT/'database/migrations/0047_publication_staging.sql').read_text()
    assert 'publication.publication_staging' in sql
    assert "staging_state IN ('STAGED','VALIDATING','READY','PUBLISHED','BLOCKED','FAILED','STALE','CANCELLED')" in sql
    assert 'UNIQUE(property_id,report_variant,channel,report_id,render_id)' in sql
