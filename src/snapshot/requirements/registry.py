from __future__ import annotations
from pathlib import Path
import yaml
from .models import SnapshotRequirement

class SnapshotRequirementRegistryError(ValueError):
    pass

_ALLOWED_ACTIONS={"BLOCK_SNAPSHOT","ALLOW_PARTIAL"}

def _load(path: Path) -> dict:
    if not path.is_file():
        raise SnapshotRequirementRegistryError(f"missing registry: {path}")
    raw=yaml.safe_load(path.read_text()) or {}
    if not raw.get("registry_id") or not raw.get("version") or not raw.get("scope"):
        raise SnapshotRequirementRegistryError(f"registry metadata missing: {path}")
    if not isinstance(raw.get("requirements"), list):
        raise SnapshotRequirementRegistryError(f"requirements must be a list: {path}")
    return raw

def load_snapshot_requirement_registry(root: Path) -> tuple[SnapshotRequirement, ...]:
    base=root/"registries/snapshot-requirements"
    paths=sorted(base.glob("*.yaml"))
    if not paths:
        raise SnapshotRequirementRegistryError("no snapshot requirement registries found")
    out=[]; seen=set()
    for path in paths:
        raw=_load(path); scope=str(raw["scope"])
        for item in raw["requirements"]:
            rid=item.get("requirement_id")
            if not isinstance(rid,str) or not rid.strip(): raise SnapshotRequirementRegistryError("requirement_id required")
            if rid in seen: raise SnapshotRequirementRegistryError(f"duplicate requirement_id: {rid}")
            seen.add(rid)
            required=item.get("required")
            if not isinstance(required,bool): raise SnapshotRequirementRegistryError(f"required must be boolean: {rid}")
            sat=item.get("satisfied_by")
            if not isinstance(sat,dict) or not sat: raise SnapshotRequirementRegistryError(f"satisfied_by required: {rid}")
            selectors=sum(1 for k in ("property_field","finding_type","dependency_type") if k in sat)
            if selectors != 1: raise SnapshotRequirementRegistryError(f"exactly one satisfaction selector required: {rid}")
            failure=item.get("failure") or {}
            action=failure.get("action"); reason=failure.get("reason_code")
            if action not in _ALLOWED_ACTIONS: raise SnapshotRequirementRegistryError(f"invalid failure action: {rid}")
            if required and action != "BLOCK_SNAPSHOT": raise SnapshotRequirementRegistryError(f"required requirement must block: {rid}")
            if not required and action != "ALLOW_PARTIAL": raise SnapshotRequirementRegistryError(f"optional requirement must allow partial: {rid}")
            if not isinstance(reason,str) or not reason: raise SnapshotRequirementRegistryError(f"failure reason required: {rid}")
            out.append(SnapshotRequirement(rid,scope,required,dict(sat),action,reason))
    return tuple(sorted(out,key=lambda r:(r.scope,r.requirement_id)))
