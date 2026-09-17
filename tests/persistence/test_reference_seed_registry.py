from pathlib import Path
from src.kernel.reference import expected_reference_values
ROOT=Path(__file__).resolve().parents[2]

def test_reference_registry_values_are_unique_and_complete():
    values=expected_reference_values(ROOT)
    for table, codes in values.items():
        assert codes, table
        assert len(codes)==len(set(codes)), table
    assert values['report_variant']==('AGENT','SELLER','PUBLIC')
    assert set(values['render_type'])=={'WEB','PDF','PRINT','MOBILE_PREVIEW'}

def test_reference_seed_is_idempotent_and_contains_registry_values():
    seed_files=sorted((ROOT/'database/migrations').glob('016*_reference_seed_data.sql')) + sorted((ROOT/'database/migrations').glob('0161_kernel_reason_codes.sql'))
    text='\n'.join(path.read_text() for path in seed_files)
    assert 'ON CONFLICT' in text
    values=expected_reference_values(ROOT)
    for codes in values.values():
        for code in codes:
            assert f"'{code}'" in text

def test_additive_reference_tables_do_not_modify_old_migration_contract():
    text=(ROOT/'database/migrations/0003_reference_registry_tables.sql').read_text().upper()
    for name in ['REFERENCE.EVENT_TYPE','REFERENCE.GUARD_ID','REFERENCE.DATA_CLASSIFICATION']:
        assert name in text
    assert 'CREATE TYPE' not in text
    assert 'ON DELETE CASCADE' not in text
