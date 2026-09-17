from __future__ import annotations
from pathlib import Path
import yaml
from .models import RegistryBundle
from .registry_errors import RegistryValidationError
from .cross_reference_validator import validate_registry_bundle

def _load(path: Path) -> dict:
    if not path.is_file():
        raise RegistryValidationError(f"Missing registry: {path}")
    raw = yaml.safe_load(path.read_text()) or {}
    if not raw.get("registry_id") or not raw.get("version"):
        raise RegistryValidationError(f"Registry metadata missing: {path}")
    return raw

def _unique(items, key, label):
    seen=set()
    out=[]
    for item in items:
        value = item[key] if isinstance(item, dict) else item
        if value in seen:
            raise RegistryValidationError(f"Duplicate {label}: {value}")
        seen.add(value); out.append(item)
    return tuple(out)

def load_registry_bundle(root: Path) -> RegistryBundle:
    base=root / "registries"
    states_raw=_load(base/"states/states.yaml")
    transitions_raw=_load(base/"transitions/transitions.yaml")
    guards_raw=_load(base/"guards/guards.yaml")
    events_raw=_load(base/"events/events.yaml")
    reasons_raw=_load(base/"reason-codes/reason-codes.yaml")
    errors_raw=_load(base/"error-codes/error-codes.yaml")
    classes_raw=_load(base/"classifications/data-classifications.yaml")

    dims=states_raw.get("dimensions") or {}
    if not dims:
        raise RegistryValidationError("State registry has no dimensions")
    for name, values in dims.items():
        if len(values) != len(set(values)):
            raise RegistryValidationError(f"Duplicate state in dimension {name}")

    bundle=RegistryBundle(
        states={k: tuple(v) for k,v in dims.items()},
        transitions=_unique(transitions_raw.get("transitions") or [], "transition_id", "transition id"),
        guards=_unique(guards_raw.get("guards") or [], "id", "guard id"),
        events=_unique(events_raw.get("events") or [], "id", "event id"),
        reason_codes=frozenset(_unique(reasons_raw.get("reason_codes") or [], lambda x:x, "reason code")) if False else frozenset(reasons_raw.get("reason_codes") or []),
        error_codes=frozenset(errors_raw.get("error_codes") or []),
        classifications=frozenset(classes_raw.get("classifications") or []),
    )
    if len(bundle.reason_codes) != len(reasons_raw.get("reason_codes") or []):
        raise RegistryValidationError("Duplicate reason code")
    if len(bundle.error_codes) != len(errors_raw.get("error_codes") or []):
        raise RegistryValidationError("Duplicate error code")
    if len(bundle.classifications) != len(classes_raw.get("classifications") or []):
        raise RegistryValidationError("Duplicate classification")
    validate_registry_bundle(bundle)
    return bundle
