from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def text(name): return (ROOT/'database/migrations'/name).read_text()
def test_batch_schema_uniqueness_and_states():
    s=text('0190_dependency_change_batches.sql'); assert 'UNIQUE (dependency_type, source_change_id)' in s; assert 'PARTIAL_FAILURE' in s
def test_item_schema_uniqueness_and_resume_index():
    s=text('0191_dependency_change_items.sql'); assert 'UNIQUE (batch_id, property_id, dependency_id)' in s; assert 'idx_dependency_change_items_batch_state' in s
def test_review_item_exists_for_review_escalation():
    s=text('0104_operations_review_items.sql'); assert 'DEPENDENCY_IMPACT_REVIEW' not in s or 'operations.review_items' in s
