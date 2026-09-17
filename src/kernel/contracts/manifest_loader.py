from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
import yaml
from .contract_errors import ManifestValidationError

ALLOWED_IMPLEMENTABLE_STATUSES = {"LOCKED", "CERTIFICATION_CANDIDATE", "CERTIFIED"}

@dataclass(frozen=True)
class ContractEntry:
    contract_id: str
    version: str
    status: str
    path: str
    sha256: str
    depends_on: tuple[str, ...]

@dataclass(frozen=True)
class ContractManifest:
    manifest_id: str
    status: str
    hash_algorithm: str
    contracts: tuple[ContractEntry, ...]

def _require(value, message: str):
    if value is None or value == "":
        raise ManifestValidationError(message)
    return value

def load_contract_manifest(path: Path) -> ContractManifest:
    raw = yaml.safe_load(path.read_text()) or {}
    manifest_id = _require(raw.get("manifest_id"), "manifest_id is required")
    status = _require(raw.get("status"), "manifest status is required")
    if status not in ALLOWED_IMPLEMENTABLE_STATUSES:
        raise ManifestValidationError(f"Manifest status is not implementable: {status}")
    if raw.get("hash_algorithm") != "SHA-256":
        raise ManifestValidationError("Only SHA-256 contract manifests are supported")

    entries = []
    seen = set()
    for item in raw.get("contracts") or []:
        cid = _require(item.get("id"), "contract id is required")
        if cid in seen:
            raise ManifestValidationError(f"Duplicate contract id: {cid}")
        seen.add(cid)
        cstatus = _require(item.get("status"), f"status required for {cid}")
        if cstatus not in ALLOWED_IMPLEMENTABLE_STATUSES:
            raise ManifestValidationError(f"Contract {cid} is not implementable: {cstatus}")
        entries.append(ContractEntry(
            contract_id=cid,
            version=str(_require(item.get("version"), f"version required for {cid}")),
            status=cstatus,
            path=_require(item.get("path"), f"path required for {cid}"),
            sha256=_require(item.get("sha256"), f"sha256 required for {cid}"),
            depends_on=tuple(item.get("depends_on") or ()),
        ))

    ids = {e.contract_id for e in entries}
    for entry in entries:
        unknown = set(entry.depends_on) - ids
        if unknown:
            raise ManifestValidationError(f"{entry.contract_id} has unknown dependencies: {sorted(unknown)}")
    _assert_acyclic(entries)
    return ContractManifest(manifest_id, status, raw["hash_algorithm"], tuple(entries))

def _assert_acyclic(entries: Iterable[ContractEntry]) -> None:
    graph = {e.contract_id: set(e.depends_on) for e in entries}
    temporary, permanent = set(), set()
    def visit(node: str):
        if node in permanent:
            return
        if node in temporary:
            raise ManifestValidationError(f"Contract dependency cycle detected at {node}")
        temporary.add(node)
        for dep in graph[node]:
            visit(dep)
        temporary.remove(node)
        permanent.add(node)
    for node in graph:
        visit(node)

def validate_architecture_lock(path: Path) -> dict:
    raw = yaml.safe_load(path.read_text()) or {}
    if raw.get("status") != "LOCKED":
        raise ManifestValidationError("Architecture lock must be LOCKED")
    if raw.get("change_process") != "ARCHITECTURE_CHANGE_REQUEST":
        raise ManifestValidationError("Architecture lock must require ARCHITECTURE_CHANGE_REQUEST")
    rules = set(raw.get("rules") or [])
    required = {
        "implementation_must_follow_locked_contracts",
        "renderer_must_not_query_raw_intelligence",
        "frontend_must_not_filter_higher_tier_data_client_side",
        "routine_recovery_uses_commands_not_direct_sql",
    }
    missing = required - rules
    if missing:
        raise ManifestValidationError(f"Architecture lock missing required rules: {sorted(missing)}")
    return raw
