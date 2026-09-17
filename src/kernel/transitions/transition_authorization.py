from __future__ import annotations

class TransitionAuthorizationError(PermissionError):
    pass

class TransitionAuthorizer:
    def authorize(self, transition, caller: str) -> None:
        if caller not in transition.allowed_callers:
            raise TransitionAuthorizationError(
                f'caller {caller} not authorized for transition {transition.transition_id}'
            )
