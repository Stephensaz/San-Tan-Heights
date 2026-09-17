from datetime import datetime, timezone
from uuid import uuid4
import pytest

from src.kernel.commands import (
    IdempotencyConflict, IdempotencyService, ProcessedCommand, ProcessedCommandRepository
)


class Cursor:
    def __init__(self, row=None): self.calls=[]; self.row=row
    def execute(self, sql, params): self.calls.append((sql, params))
    def fetchone(self): return self.row


def make_row(request_hash='a'*64):
    c=uuid4(); corr=uuid4()
    return (str(c),'kernel','TRANSITION','key-1',request_hash,'APPLIED',{'ok':True},datetime.now(timezone.utc),str(corr))


def test_new_idempotency_key_is_new():
    c=Cursor(None)
    assert IdempotencyService().check(c,'kernel','key-1','a'*64).status == 'NEW'


def test_same_hash_replays_prior_result():
    c=Cursor(make_row())
    d=IdempotencyService().check(c,'kernel','key-1','a'*64)
    assert d.status == 'REPLAY' and d.prior.result_payload == {'ok': True}


def test_same_key_different_hash_conflicts():
    c=Cursor(make_row('b'*64))
    with pytest.raises(IdempotencyConflict):
        IdempotencyService().check(c,'kernel','key-1','a'*64)


def test_processed_command_insert_is_insert_only():
    c=Cursor(); item=ProcessedCommand(uuid4(),'kernel','TRANSITION','k','a'*64,'APPLIED',uuid4(),{'ok':True})
    ProcessedCommandRepository().insert(c,item)
    assert c.calls[0][0].lstrip().startswith('INSERT INTO audit.processed_commands')
