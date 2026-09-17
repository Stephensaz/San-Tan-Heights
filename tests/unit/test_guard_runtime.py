from pathlib import Path
import pytest

from src.kernel.guards import GuardContext, GuardRegistry, GuardRunner, GuardRunnerError, GuardResult

ROOT=Path(__file__).resolve().parents[2]

def ctx(**kw):
    base=dict(entity_id='E1',entity_type='KERNEL_TEST_ENTITY',state_dimension='CONTENT',expected_state='BUILDING',actual_state='BUILDING',caller_id='KERNEL',allowed_callers=frozenset({'KERNEL'}),entity_exists=True)
    base.update(kw)
    return GuardContext(**base)

def test_guard_registry_loads_read_only_guards():
    reg=GuardRegistry.from_repository(ROOT)
    assert reg.get('ENTITY_EXISTS').read_only is True

def test_all_kernel_guards_pass():
    reg=GuardRegistry.from_repository(ROOT)
    results=GuardRunner(reg).run(('ENTITY_EXISTS','EXPECTED_STATE_MATCHES','CALLER_AUTHORIZED'),ctx())
    assert [r.result for r in results] == ['PASS','PASS','PASS']
    assert GuardRunner.overall_result(results)=='PASS'

def test_guard_failure_short_circuits_remaining_guards():
    reg=GuardRegistry.from_repository(ROOT)
    results=GuardRunner(reg).run(('ENTITY_EXISTS','EXPECTED_STATE_MATCHES','CALLER_AUTHORIZED'),ctx(entity_exists=False))
    assert [r.result for r in results] == ['FAIL','NOT_EVALUATED','NOT_EVALUATED']

def test_expected_state_guard_fails_closed():
    reg=GuardRegistry.from_repository(ROOT)
    results=GuardRunner(reg).run(('EXPECTED_STATE_MATCHES',),ctx(actual_state='VALIDATING'))
    assert results[0].result=='FAIL'
    assert results[0].reason_code=='EXPECTED_STATE_MISMATCH'

def test_unauthorized_caller_fails():
    reg=GuardRegistry.from_repository(ROOT)
    results=GuardRunner(reg).run(('CALLER_AUTHORIZED',),ctx(caller_id='RENDERER'))
    assert results[0].result=='FAIL'

def test_guard_exception_becomes_error_not_allow():
    reg=GuardRegistry.from_repository(ROOT)
    def broken(_): raise RuntimeError('boom')
    runner=GuardRunner(reg,{'entity_exists':broken,'expected_state_matches':lambda c: GuardResult('EXPECTED_STATE_MATCHES','PASS'),'caller_authorized':lambda c: GuardResult('CALLER_AUTHORIZED','PASS')})
    results=runner.run(('ENTITY_EXISTS','CALLER_AUTHORIZED'),ctx())
    assert [r.result for r in results]==['ERROR','NOT_EVALUATED']
    assert GuardRunner.overall_result(results)=='ERROR'
