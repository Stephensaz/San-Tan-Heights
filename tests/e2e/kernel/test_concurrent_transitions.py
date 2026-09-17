from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
def test_state_adapter_uses_row_lock_and_compare_and_swap():
 src=(ROOT/'src/kernel/state/kernel_test_adapter.py').read_text()
 assert 'FOR UPDATE' in src
 assert 'state_version=%s' in src
 assert 'state_version=state_version+1' in src
