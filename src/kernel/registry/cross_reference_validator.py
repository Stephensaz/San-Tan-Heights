from __future__ import annotations
from .registry_errors import RegistryValidationError

def validate_registry_bundle(bundle) -> None:
    guard_ids={g["id"] for g in bundle.guards}
    event_ids={e["id"] for e in bundle.events}
    for guard in bundle.guards:
        if guard.get("read_only") is not True:
            raise RegistryValidationError(f"Guard must be read-only: {guard.get('id')}")
    for tr in bundle.transitions:
        dim=tr.get("state_dimension")
        if dim not in bundle.states:
            raise RegistryValidationError(f"Unknown state dimension: {dim}")
        states=set(bundle.states[dim])
        if tr.get("from_state") not in states:
            raise RegistryValidationError(f"Unknown from_state in {tr['transition_id']}")
        if tr.get("to_state") not in states:
            raise RegistryValidationError(f"Unknown to_state in {tr['transition_id']}")
        missing_guards=set(tr.get("required_guards") or [])-guard_ids
        if missing_guards:
            raise RegistryValidationError(f"Unknown guards in {tr['transition_id']}: {sorted(missing_guards)}")
        all_events=set(tr.get("emitted_events") or [])
        if tr.get("rejection_event"):
            all_events.add(tr["rejection_event"])
        missing_events=all_events-event_ids
        if missing_events:
            raise RegistryValidationError(f"Unknown events in {tr['transition_id']}: {sorted(missing_events)}")
        reason=tr.get("reason_code")
        if reason and reason not in bundle.reason_codes:
            raise RegistryValidationError(f"Unknown reason code in {tr['transition_id']}: {reason}")
