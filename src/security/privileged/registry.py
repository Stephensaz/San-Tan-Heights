from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import yaml

class PrivilegedCommandRegistryError(ValueError): pass

@dataclass(frozen=True)
class PrivilegedCommandRule:
    command_type: str
    required_action: str
    classification: str
    property_scoped: bool

class PrivilegedCommandRegistry:
    EXPECTED_ID = "STH-PRIVILEGED-COMMAND-POLICY-v1.0"
    def __init__(self, registry_id: str, version: str, rules: dict[str, PrivilegedCommandRule]):
        self.registry_id=registry_id; self.version=version; self._rules=rules
    @classmethod
    def from_repository(cls, root: Path):
        raw=yaml.safe_load((Path(root)/"registries/security/privileged-command-policy-v1.0.yaml").read_text())
        if raw.get("registry_id") != cls.EXPECTED_ID or raw.get("status") != "LOCKED":
            raise PrivilegedCommandRegistryError("PRIVILEGED_COMMAND_REGISTRY_INVALID")
        rows=raw.get("commands") or {}
        if not rows: raise PrivilegedCommandRegistryError("PRIVILEGED_COMMAND_RULES_MISSING")
        rules={}
        for command_type,row in rows.items():
            action=row.get("required_action"); classification=row.get("classification")
            if not action or not classification or not isinstance(row.get("property_scoped"), bool):
                raise PrivilegedCommandRegistryError(f"PRIVILEGED_COMMAND_RULE_INVALID:{command_type}")
            rules[command_type]=PrivilegedCommandRule(command_type,str(action),str(classification),row["property_scoped"])
        return cls(raw["registry_id"],str(raw["version"]),rules)
    def get(self, command_type: str) -> PrivilegedCommandRule:
        try: return self._rules[command_type]
        except KeyError as exc: raise PrivilegedCommandRegistryError("UNKNOWN_PRIVILEGED_COMMAND") from exc
    @property
    def command_types(self): return tuple(sorted(self._rules))
