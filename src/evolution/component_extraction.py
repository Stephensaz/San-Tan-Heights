from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Iterable
import yaml


@dataclass(frozen=True)
class ComponentClassification:
    path: str
    component_class: str
    matched_prefix: str
    community_markers: tuple[str,...]


@dataclass(frozen=True)
class ExtractionAudit:
    classified: tuple[ComponentClassification,...]
    unclassified: tuple[str,...]
    ambiguous: tuple[str,...]
    core_marker_violations: tuple[str,...]
    inventory_fingerprint: str


def _hash(payload: object) -> str:
    raw=json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")
    return sha256(raw).hexdigest()


def load_extraction_registry(path: str|Path) -> dict:
    raw=yaml.safe_load(Path(path).read_text())
    if raw.get("extraction_registry_id")!="STH-M10-002-CORE-CONFIG-EXTRACTION-v1.0" or raw.get("status")!="FROZEN":
        raise ValueError("invalid frozen M10-002 extraction registry")
    return raw


def classify_path(path: str, registry: dict) -> tuple[str,str]:
    matches=[]
    for cls,prefixes in registry["path_rules"].items():
        for prefix in prefixes:
            if path.startswith(prefix):
                matches.append((len(prefix),cls,prefix))
    if not matches:
        raise ValueError(f"unclassified component path: {path}")
    max_len=max(x[0] for x in matches)
    best=[x for x in matches if x[0]==max_len]
    classes={x[1] for x in best}
    if len(classes)!=1:
        raise ValueError(f"ambiguous component classification: {path}")
    _,cls,prefix=best[0]
    return cls,prefix


def scan_markers(path: Path, markers: Iterable[str]) -> tuple[str,...]:
    try:
        text=path.read_text(encoding="utf-8")
    except (UnicodeDecodeError,OSError):
        return ()
    return tuple(sorted(m for m in markers if m in text))


def inventory_repository(root: str|Path, registry: dict) -> ExtractionAudit:
    root=Path(root)
    declared=tuple(registry["declared_scope"])
    markers=tuple(registry["community_markers"])
    allow=set(registry.get("core_marker_allowlist") or ())
    classified=[]; unclassified=[]; ambiguous=[]; core_violations=[]
    material_suffixes={".py",".yaml",".yml",".json",".html",".md",".sql"}

    for scope in declared:
        base=root/scope
        if not base.exists():
            continue
        for p in sorted(x for x in base.rglob("*") if x.is_file() and x.suffix.lower() in material_suffixes):
            rel=p.relative_to(root).as_posix()
            try:
                cls,prefix=classify_path(rel,registry)
            except ValueError as exc:
                if "ambiguous" in str(exc): ambiguous.append(rel)
                else: unclassified.append(rel)
                continue
            found=scan_markers(p,markers)
            classified.append(ComponentClassification(rel,cls,prefix,found))
            if cls=="CORE_REUSABLE" and found and rel not in allow:
                core_violations.append(rel)

    payload=[{"path":x.path,"component_class":x.component_class,"matched_prefix":x.matched_prefix,
              "community_markers":list(x.community_markers)} for x in classified]
    return ExtractionAudit(tuple(classified),tuple(unclassified),tuple(ambiguous),
                           tuple(core_violations),_hash(payload))


def require_clean_inventory(audit: ExtractionAudit) -> None:
    if audit.unclassified:
        raise ValueError(f"unclassified material components: {audit.unclassified[:5]}")
    if audit.ambiguous:
        raise ValueError(f"ambiguous material components: {audit.ambiguous[:5]}")
    if audit.core_marker_violations:
        raise ValueError(f"community/source assumptions hidden in reusable core: {audit.core_marker_violations[:5]}")


def assert_baseline_preserved(*, frozen_fingerprint: str, current_baseline_path: str|Path) -> None:
    actual=sha256(Path(current_baseline_path).read_bytes()).hexdigest()
    if actual!=frozen_fingerprint:
        raise ValueError("accepted San Tan Heights baseline changed during extraction")
