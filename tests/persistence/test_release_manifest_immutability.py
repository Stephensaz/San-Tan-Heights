from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SQL=(ROOT/'database/migrations/0081_release_manifest_immutability.sql').read_text()

def test_frozen_manifest_parent_and_membership_are_database_guarded():
    assert 'trg_release_manifest_immutable' in SQL
    assert 'trg_release_item_frozen_membership' in SQL
    assert 'trg_release_parent_frozen_metadata' in SQL
    assert 'frozen release target evidence is immutable' in SQL

def test_release_item_lifecycle_fields_remain_mutable_after_freeze():
    # Guard tuple intentionally protects target identity/evidence, not item_state/error fields.
    guarded='NEW.release_id,NEW.property_id,NEW.report_variant,NEW.channel,NEW.membership_ordinal'
    assert guarded in SQL
    assert 'NEW.item_state' not in SQL
    assert 'NEW.last_error_code' not in SQL
