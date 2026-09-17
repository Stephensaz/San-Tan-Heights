from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone
from src.snapshot.query import CurrentSnapshotReader
ROOT=Path(__file__).resolve().parents[3]

class Cursor:
    def __init__(self,row): self.row=row; self.sql=''
    def execute(self,sql,args): self.sql=sql
    def fetchone(self): return self.row

def test_view_selects_latest_accepted_only():
    sql=(ROOT/'database/migrations/0204_current_snapshot_view.sql').read_text()
    assert "qa_status = 'PASS'" in sql
    assert "COMPLETE','PARTIAL_VALID" in sql
    assert 'DISTINCT ON' in sql
    assert 'ORDER BY s.property_id, s.snapshot_sequence DESC' in sql

def test_reader_maps_current_snapshot():
    p,s=uuid4(),uuid4(); now=datetime.now(timezone.utc)
    c=Cursor((p,s,3,'a'*64,'b'*64,'c'*64,'d'*64,'COMPLETE','PASS',now))
    result=CurrentSnapshotReader().get(c,p)
    assert result.current_snapshot_id==s
    assert result.snapshot_sequence==3
    assert 'snapshot.current_snapshot_view' in c.sql
