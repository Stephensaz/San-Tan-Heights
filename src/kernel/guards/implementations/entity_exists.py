from src.kernel.guards.models import GuardContext, GuardResult

def evaluate(context: GuardContext) -> GuardResult:
    if context.entity_exists:
        return GuardResult('ENTITY_EXISTS','PASS')
    return GuardResult('ENTITY_EXISTS','FAIL','ENTITY_NOT_FOUND',{'entity_type':context.entity_type})
