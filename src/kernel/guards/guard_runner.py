from __future__ import annotations
import importlib
from collections.abc import Callable

from .guard_registry import GuardRegistry, GuardRegistryError
from .models import GuardContext, GuardResult

class GuardRunnerError(RuntimeError):
    pass

class GuardRunner:
    def __init__(self, registry: GuardRegistry, implementations: dict[str, Callable[[GuardContext], GuardResult]] | None = None):
        self.registry=registry
        self._implementations=implementations or self._load_implementations()
        missing=[]
        for definition in self.registry.definitions():
            if definition.implementation not in self._implementations:
                missing.append(definition.guard_id)
        if missing:
            raise GuardRunnerError(f'missing guard implementations: {sorted(missing)}')

    def _load_implementations(self) -> dict[str, Callable[[GuardContext], GuardResult]]:
        result={}
        for definition in self.registry.definitions():
            module_name=f'src.kernel.guards.implementations.{definition.implementation}'
            try:
                module=importlib.import_module(module_name)
                fn=getattr(module,'evaluate')
            except (ImportError, AttributeError) as exc:
                raise GuardRunnerError(f'cannot load guard implementation: {definition.guard_id}') from exc
            result[definition.implementation]=fn
        return result

    def run(self, guard_ids: tuple[str, ...] | list[str], context: GuardContext) -> tuple[GuardResult, ...]:
        results=[]
        stopped=False
        for guard_id in guard_ids:
            definition=self.registry.get(guard_id)
            if stopped:
                results.append(GuardResult(guard_id,'NOT_EVALUATED','PRIOR_GUARD_STOPPED'))
                continue
            try:
                outcome=self._implementations[definition.implementation](context)
                if not isinstance(outcome, GuardResult):
                    raise TypeError('guard implementation must return GuardResult')
                if outcome.guard_id != guard_id:
                    raise GuardRunnerError(f'guard implementation returned wrong guard id: {guard_id}')
            except Exception as exc:
                outcome=GuardResult(guard_id,'ERROR','GUARD_EXECUTION_ERROR',{'error_type':type(exc).__name__})
            results.append(outcome)
            if outcome.result in {'FAIL','BLOCK','ERROR'}:
                stopped=True
        return tuple(results)

    @staticmethod
    def overall_result(results: tuple[GuardResult, ...] | list[GuardResult]) -> str:
        values={r.result for r in results}
        if 'ERROR' in values: return 'ERROR'
        if 'BLOCK' in values: return 'BLOCK'
        if 'FAIL' in values: return 'FAIL'
        return 'PASS'
