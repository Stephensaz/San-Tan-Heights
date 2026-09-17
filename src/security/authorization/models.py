from dataclasses import dataclass

@dataclass(frozen=True)
class HumanRole:
    role_id: str
    status: str
    property_scope_mode: str
    classifications: frozenset[str]
    actions: frozenset[str]

@dataclass(frozen=True)
class HumanPrincipal:
    subject_id: str
    role_id: str

@dataclass(frozen=True)
class AuthorizationDecision:
    allowed: bool
    role_id: str
    action: str
    classification: str
    protected_property: bool
    reason: str
