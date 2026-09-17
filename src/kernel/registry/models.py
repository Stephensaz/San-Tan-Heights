from dataclasses import dataclass

@dataclass(frozen=True)
class RegistryBundle:
    states: dict
    transitions: tuple[dict, ...]
    guards: tuple[dict, ...]
    events: tuple[dict, ...]
    reason_codes: frozenset[str]
    error_codes: frozenset[str]
    classifications: frozenset[str]
