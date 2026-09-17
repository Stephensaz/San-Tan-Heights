from src.kernel.guards.models import GuardContext, GuardResult

def evaluate(context: GuardContext) -> GuardResult:
    if context.caller_id in context.allowed_callers:
        return GuardResult('CALLER_AUTHORIZED','PASS')
    return GuardResult('CALLER_AUTHORIZED','FAIL','CALLER_NOT_AUTHORIZED',{'caller_id':context.caller_id})
