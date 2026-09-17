from pathlib import Path
import json
from src.snapshot.requirements import load_snapshot_requirement_registry
ROOT=Path(__file__).resolve().parents[3]

def test_requirement_schema_and_registry_load():
    schema=json.loads((ROOT/'schemas/snapshots/snapshot-requirement.schema.json').read_text())
    assert schema['type']=='object'
    reqs=load_snapshot_requirement_registry(ROOT)
    ids=[r.requirement_id for r in reqs]
    assert len(ids)==len(set(ids))
    assert 'REQ_CANONICAL_PROPERTY_IDENTITY' in ids
    assert 'REQ_PROPERTY_IDENTITY_DEPENDENCY' in ids
    assert 'REQ_VIEW_CLASSIFICATION' in ids

def test_required_requirements_block_and_optional_allow_partial():
    reqs=load_snapshot_requirement_registry(ROOT)
    for r in reqs:
        assert r.failure_action == ('BLOCK_SNAPSHOT' if r.required else 'ALLOW_PARTIAL')

def test_reason_codes_exist_in_governed_registry():
    import yaml
    reasons=set(yaml.safe_load((ROOT/'registries/reason-codes/reason-codes.yaml').read_text())['reason_codes'])
    for r in load_snapshot_requirement_registry(ROOT): assert r.failure_reason_code in reasons
