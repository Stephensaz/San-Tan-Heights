import pytest
from src.kernel.state import StateAdapterRegistry, KernelTestEntityAdapter, StateAdapterError, StateConflictError, EntityNotFoundError

class FakeCursor:
    def __init__(self, row=('id','BUILDING',1), update_row=('id','VALIDATING',2)):
        self.row=row; self.update_row=update_row; self.last_sql=''; self.last_params=None
    def execute(self,sql,params):
        self.last_sql=sql; self.last_params=params
    def fetchone(self):
        if self.last_sql.strip().startswith('UPDATE'):
            return self.update_row
        return self.row

def test_registry_registers_and_resolves_adapter():
    r=StateAdapterRegistry(); a=KernelTestEntityAdapter(); r.register(a)
    assert r.get('KERNEL_TEST_ENTITY','CONTENT') is a

def test_duplicate_adapter_rejected():
    r=StateAdapterRegistry(); r.register(KernelTestEntityAdapter())
    with pytest.raises(StateAdapterError): r.register(KernelTestEntityAdapter())

def test_missing_adapter_fails_closed():
    with pytest.raises(StateAdapterError): StateAdapterRegistry().get('NOPE','CONTENT')

def test_lock_current_state_uses_for_update():
    c=FakeCursor(); rec=KernelTestEntityAdapter().lock_current_state(c,'id')
    assert 'FOR UPDATE' in c.last_sql
    assert rec.state=='BUILDING' and rec.state_version==1

def test_apply_state_is_compare_and_swap():
    c=FakeCursor(); rec=KernelTestEntityAdapter().apply_state(c,'id','BUILDING','VALIDATING',1)
    assert rec.state=='VALIDATING' and rec.state_version==2
    assert c.last_params==('VALIDATING','id','BUILDING',1)

def test_apply_state_conflict_raises():
    c=FakeCursor(row=('id','VALIDATING',2),update_row=None)
    with pytest.raises(StateConflictError): KernelTestEntityAdapter().apply_state(c,'id','BUILDING','VALIDATING',1)

def test_apply_state_missing_entity_raises():
    c=FakeCursor(row=None,update_row=None)
    with pytest.raises(EntityNotFoundError): KernelTestEntityAdapter().apply_state(c,'id','BUILDING','VALIDATING',1)
