from __future__ import annotations
from .models import StateRecord
from .state_adapter import StateAdapter, EntityNotFoundError, StateConflictError

class KernelTestEntityAdapter(StateAdapter):
    entity_type='KERNEL_TEST_ENTITY'
    state_dimension='CONTENT'

    READ_SQL='SELECT entity_id,state,state_version FROM operations.kernel_test_entities WHERE entity_id=%s'
    LOCK_SQL=READ_SQL+' FOR UPDATE'
    UPDATE_SQL='''UPDATE operations.kernel_test_entities
        SET state=%s,state_version=state_version+1,updated_at=now()
        WHERE entity_id=%s AND state=%s AND state_version=%s
        RETURNING entity_id,state,state_version'''

    @staticmethod
    def _record(row):
        if not row: return None
        if isinstance(row, dict):
            return StateRecord(row['entity_id'],row['state'],row['state_version'])
        return StateRecord(row[0],row[1],row[2])

    def get_current_state(self, cursor, entity_id):
        cursor.execute(self.READ_SQL,(entity_id,))
        return self._record(cursor.fetchone())

    def lock_current_state(self, cursor, entity_id):
        cursor.execute(self.LOCK_SQL,(entity_id,))
        return self._record(cursor.fetchone())

    def apply_state(self, cursor, entity_id, expected_state: str, target_state: str, expected_version: int):
        cursor.execute(self.UPDATE_SQL,(target_state,entity_id,expected_state,expected_version))
        row=cursor.fetchone()
        if row:
            return self._record(row)
        current=self.get_current_state(cursor,entity_id)
        if current is None:
            raise EntityNotFoundError(f'entity not found: {entity_id}')
        raise StateConflictError(f'state/version conflict for entity: {entity_id}')
