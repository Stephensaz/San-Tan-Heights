from dataclasses import replace
from uuid import UUID
from src.regeneration.target import JobTargetContext, JobTargetKeyEngine

PID=UUID('11111111-1111-1111-1111-111111111111')
SID=UUID('22222222-2222-2222-2222-222222222222')
BASE=JobTargetContext(PID,'PUBLIC',SID,'report-1','content-1','variant-1')

def test_target_key_is_deterministic():
    e=JobTargetKeyEngine(); assert e.calculate(BASE)==e.calculate(BASE) and len(e.calculate(BASE))==64

def test_snapshot_and_variant_change_key():
    e=JobTargetKeyEngine(); base=e.calculate(BASE)
    assert e.calculate(replace(BASE,target_snapshot_id=UUID('33333333-3333-3333-3333-333333333333')))!=base
    assert e.calculate(replace(BASE,report_variant='AGENT'))!=base

def test_runtime_metadata_not_part_of_context_or_hash():
    assert set(BASE.__dataclass_fields__)=={'property_id','report_variant','target_snapshot_id','report_schema_version','content_contract_version','variant_policy_version'}
