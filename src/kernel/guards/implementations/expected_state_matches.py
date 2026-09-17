from src.kernel.guards.models import GuardContext, GuardResult

def evaluate(context: GuardContext) -> GuardResult:
    if context.actual_state == context.expected_state:
        return GuardResult('EXPECTED_STATE_MATCHES','PASS')
    return GuardResult('EXPECTED_STATE_MATCHES','FAIL','EXPECTED_STATE_MISMATCH',{
        'expected_state':context.expected_state,
        'actual_state':context.actual_state,
    })
