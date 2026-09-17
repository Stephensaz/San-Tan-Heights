from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
import yaml
from src.renderer.hashing import PresentationDependency

class DiagramBindingError(ValueError): pass

@dataclass(frozen=True)
class DiagramAsset:
    diagram_id: str
    diagram_type: str
    property_id: str
    approval_status: str
    qa_status: str
    semantic_fingerprint: str
    version: str
    finding_ids: tuple[str,...]

@dataclass(frozen=True)
class BoundDiagram:
    slot_id: str
    diagram_type: str
    diagram_id: str | None
    dependency: PresentationDependency | None
    omitted_reason: str | None = None

class DiagramSlotBinder:
    def __init__(self, policy: dict): self.policy=policy
    @classmethod
    def from_repository(cls, root: Path):
        data=yaml.safe_load((root/'registries/diagrams/diagram-policy-v1.0.yaml').read_text())
        if data.get('registry_id')!='STH-DIAGRAM-POLICY-v1.0' or data.get('status')!='LOCKED': raise DiagramBindingError('invalid diagram policy registry')
        return cls(data)
    @staticmethod
    def _hash64(v):
        if len(v)!=64 or any(c not in '0123456789abcdef' for c in v): raise DiagramBindingError('invalid diagram fingerprint')
    def bind(self, *, property_id: str, slots: Iterable[dict], assets: Iterable[DiagramAsset]) -> tuple[BoundDiagram,...]:
        assets=tuple(assets); out=[]
        for slot in slots:
            sid, dtype, required = slot['slot_id'],slot['diagram_type'],bool(slot['required'])
            rule=self.policy['slot_rules'].get(dtype)
            if not rule: raise DiagramBindingError(f'unknown diagram type: {dtype}')
            slot_findings=set(slot.get('finding_ids',[]))
            eligible=[]
            for a in assets:
                self._hash64(a.semantic_fingerprint)
                if a.diagram_type not in rule['allowed_types'] or a.property_id!=property_id: continue
                if a.approval_status!='APPROVED' or a.qa_status!='PASS': continue
                if not slot_findings.issubset(set(a.finding_ids)): continue
                eligible.append(a)
            eligible.sort(key=lambda a:(a.version,a.diagram_id), reverse=True)
            if len(eligible)>1 and eligible[0].version==eligible[1].version: raise DiagramBindingError(f'ambiguous approved diagram for slot {sid}')
            if not eligible:
                if required: raise DiagramBindingError(f'required diagram slot unbound: {sid}')
                out.append(BoundDiagram(sid,dtype,None,None,'NO_APPROVED_COMPATIBLE_DIAGRAM')); continue
            a=eligible[0]
            dep=PresentationDependency('DIAGRAM',a.diagram_id,a.semantic_fingerprint,a.version,sid)
            out.append(BoundDiagram(sid,dtype,a.diagram_id,dep,None))
        return tuple(out)
