from __future__ import annotations
from dataclasses import replace
from pathlib import Path
import yaml
from src.snapshot.governed_state.models import GovernedDependency

class DependencyManifestError(ValueError):
    pass

class DependencyManifestBuilder:
    def __init__(self, registry_path: str | Path | None = None):
        if registry_path is None:
            registry_path = Path(__file__).resolve().parents[3] / "registries" / "dependency-types.yaml"
        raw = yaml.safe_load(Path(registry_path).read_text())
        self.allowed = frozenset(raw.get("types", ()))
        if not self.allowed:
            raise DependencyManifestError("dependency type registry is empty")

    def build(self, dependencies: tuple[GovernedDependency, ...]) -> tuple[GovernedDependency, ...]:
        by_key: dict[tuple[str, str], GovernedDependency] = {}
        for dep in dependencies:
            if dep.dependency_type not in self.allowed:
                raise DependencyManifestError(f"unknown dependency type: {dep.dependency_type}")
            normalized = replace(dep, variant_scope=tuple(sorted(set(dep.variant_scope))))
            key = (normalized.dependency_type, normalized.dependency_id)
            prior = by_key.get(key)
            if prior is not None and prior != normalized:
                raise DependencyManifestError(f"conflicting duplicate dependency: {key[0]}:{key[1]}")
            by_key[key] = normalized
        return tuple(by_key[k] for k in sorted(by_key))
