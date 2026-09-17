from pathlib import Path
import pytest

from src.kernel.transitions import TransitionRegistry, TransitionRegistryError, TransitionResolver, TransitionAuthorizer, TransitionAuthorizationError

ROOT=Path(__file__).resolve().parents[2]


def test_transition_registry_gets_known_transition():
    reg=TransitionRegistry.from_repository(ROOT)
    t=reg.get('KERNEL_TEST_BUILDING_TO_VALIDATING')
    assert t.from_state=='BUILDING' and t.to_state=='VALIDATING'
    assert t.required_guards == ('ENTITY_EXISTS','EXPECTED_STATE_MATCHES','CALLER_AUTHORIZED')


def test_transition_resolves_by_state_signature():
    reg=TransitionRegistry.from_repository(ROOT)
    t=TransitionResolver(reg).by_states('KERNEL_TEST_ENTITY','CONTENT','BUILDING','VALIDATING')
    assert t.transition_id=='KERNEL_TEST_BUILDING_TO_VALIDATING'


def test_unknown_transition_fails_closed():
    reg=TransitionRegistry.from_repository(ROOT)
    with pytest.raises(TransitionRegistryError): reg.get('NOPE')
    with pytest.raises(TransitionRegistryError): reg.resolve('KERNEL_TEST_ENTITY','CONTENT','VALIDATING','READY')


def test_authorizer_allows_declared_caller_and_rejects_other():
    t=TransitionRegistry.from_repository(ROOT).get('KERNEL_TEST_BUILDING_TO_VALIDATING')
    TransitionAuthorizer().authorize(t,'KERNEL')
    with pytest.raises(TransitionAuthorizationError):
        TransitionAuthorizer().authorize(t,'RENDERER')
