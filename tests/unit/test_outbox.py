from datetime import datetime, timezone
from uuid import uuid4
import pytest

from src.kernel.outbox import OutboxRepository, TransactionalOutboxWriter
from workers.outbox_dispatcher.worker import OutboxDispatcher


class Cursor:
    def __init__(self, rows=None): self.calls=[]; self.rows=rows or []
    def execute(self, sql, params=None): self.calls.append((sql, params))
    def fetchall(self): return self.rows


class Publisher:
    def __init__(self, fail=False): self.fail=fail; self.published=[]
    def publish(self, *, event_id, topic):
        if self.fail: raise TimeoutError('secret external details')
        self.published.append((event_id,topic))


def test_outbox_enqueue_deduplicates_topics_in_order():
    c=Cursor(); event=uuid4()
    TransactionalOutboxWriter().enqueue(c,event,['z','a','z'])
    assert len(c.calls)==2
    assert [call[1][1] for call in c.calls] == ['a','z']


def test_outbox_claim_uses_skip_locked():
    c=Cursor([])
    OutboxRepository().claim(c,'worker-1',10,60)
    assert 'FOR UPDATE SKIP LOCKED' in c.calls[0][0]


def test_outbox_claim_validates_limits():
    c=Cursor([])
    with pytest.raises(ValueError): OutboxRepository().claim(c,'w',0,60)
    with pytest.raises(ValueError): OutboxRepository().claim(c,'w',1,0)


def test_dispatch_success_marks_delivered():
    oid,eid=uuid4(),uuid4()
    c=Cursor([(oid,eid,'events','CLAIMED',0,'w',datetime.now(timezone.utc))])
    p=Publisher()
    result=OutboxDispatcher().dispatch_once(c,p,'w')
    assert result.delivered == 1 and result.retried == 0
    assert any("delivery_state='DELIVERED'" in sql for sql,_ in c.calls)


def test_dispatch_failure_records_safe_retry_not_exception_text():
    oid,eid=uuid4(),uuid4()
    c=Cursor([(oid,eid,'events','CLAIMED',0,'w',datetime.now(timezone.utc))])
    result=OutboxDispatcher().dispatch_once(c,Publisher(fail=True),'w')
    assert result.retried == 1
    retry_call=[call for call in c.calls if 'DEAD_LETTER' in call[0]][0]
    assert 'secret external details' not in str(retry_call[1])
