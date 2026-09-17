from pathlib import Path
import pytest
from src.operations.reconciliation.registry import ReconciliationRuleRegistry
ROOT=Path(__file__).resolve().parents[3]
def test_registry_contains_all_m5_integrity_rules():
    r=ReconciliationRuleRegistry(ROOT/'registries/reconciliation-rules/core.yaml')
    assert set(r.rule_ids)=={'POINTER_REPORT_EXISTS','POINTER_RENDER_EXISTS','POINTER_RENDER_REPORT_MATCH','ORPHAN_READY_REPORT','ORPHAN_READY_RENDER','STUCK_REGENERATION_JOB','RELEASE_ITEM_COUNT_MATCH','RELEASE_MANIFEST_MATCH'}
    assert r.get('POINTER_REPORT_EXISTS')['severity']=='CRITICAL'
def test_registry_fails_closed_unknown():
    r=ReconciliationRuleRegistry(ROOT/'registries/reconciliation-rules/core.yaml')
    with pytest.raises(ValueError): r.get('NOPE')
