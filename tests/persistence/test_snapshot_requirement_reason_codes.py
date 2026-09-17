from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def test_snapshot_requirement_reason_codes_are_seeded_additively():
    text=(ROOT/'database/migrations/0162_reference_seed_data.sql').read_text()
    assert 'PROPERTY_IDENTITY_UNRESOLVED' in text
    assert 'PARCEL_IDENTITY_DEPENDENCY_MISSING' in text
    assert 'ON CONFLICT (code) DO NOTHING' in text
