from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
def test_engine_escalates_event_persistence_failure_for_caller_rollback():
 src=(ROOT/'src/kernel/transitions/transition_engine.py').read_text()
 assert 'TransitionEngineInfrastructureError' in src
 assert 'rollback required' in src
