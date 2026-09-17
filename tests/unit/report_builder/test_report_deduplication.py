from uuid import uuid4
from src.report_builder.deduplication import ReportDeduplicationEngine

class Repo:
    def __init__(self,result): self.result=result; self.calls=[]
    def find_equivalent(self,cursor,property_id,variant,input_hash):
        self.calls.append((property_id,variant,input_hash)); return self.result

def test_reuses_semantically_equivalent_report():
    rid=uuid4(); repo=Repo(rid); result=ReportDeduplicationEngine(repo).find(object(),property_id=uuid4(),report_variant='PUBLIC',report_input_hash='a'*64)
    assert result.reused and result.existing_report_id==rid

def test_no_equivalent_report_allows_new_version():
    result=ReportDeduplicationEngine(Repo(None)).find(object(),property_id=uuid4(),report_variant='AGENT',report_input_hash='b'*64)
    assert not result.reused and result.existing_report_id is None
