from __future__ import annotations
from uuid import uuid4
from .engine import ReportSemanticDiffEngine
class ReportDiffService:
    def __init__(self,repository,engine=None):
        self.repository=repository
        self.engine=engine or ReportSemanticDiffEngine()
    def persist(self,cursor,*,old_report_id,new_report_id,old_payload,new_payload):
        diff=self.engine.compare(old_payload,new_payload)
        self.repository.insert_diff(cursor,uuid4(),old_report_id,new_report_id,diff.payload,diff.diff_hash)
        return diff
