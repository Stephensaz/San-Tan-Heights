from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
import yaml

from src.renderer.hashing import PresentationDependency


class MediaBindingError(ValueError): pass

@dataclass(frozen=True)
class MediaAsset:
    media_id: str
    media_class: str
    property_id: str | None
    approval_status: str
    rights_status: str
    semantic_fingerprint: str
    version: str

@dataclass(frozen=True)
class BoundMedia:
    slot_id: str
    slot_type: str
    media_id: str | None
    dependency: PresentationDependency | None
    omitted_reason: str | None = None

class MediaSlotBinder:
    def __init__(self, policy: dict): self.policy=policy

    @classmethod
    def from_repository(cls, root: Path):
        p=root/'registries/media/media-policy-v1.0.yaml'
        data=yaml.safe_load(p.read_text())
        if data.get('registry_id')!='STH-MEDIA-POLICY-v1.0' or data.get('status')!='LOCKED':
            raise MediaBindingError('invalid media policy registry')
        return cls(data)

    @staticmethod
    def _hash64(v: str):
        if len(v)!=64 or any(c not in '0123456789abcdef' for c in v): raise MediaBindingError('invalid media fingerprint')

    def bind(self, *, property_id: str, slots: Iterable[dict], assets: Iterable[MediaAsset]) -> tuple[BoundMedia,...]:
        by_class={}
        for a in assets:
            self._hash64(a.semantic_fingerprint)
            by_class.setdefault(a.media_class, []).append(a)
        out=[]
        for slot in slots:
            sid, stype, required = slot['slot_id'], slot['slot_type'], bool(slot['required'])
            rule=self.policy['slot_rules'].get(stype)
            if not rule: raise MediaBindingError(f'unknown media slot type: {stype}')
            candidates=[]
            for clsname in rule['allowed_classes']:
                candidates += by_class.get(clsname, [])
            eligible=[]
            for a in candidates:
                if a.approval_status!='APPROVED' or a.rights_status!='CLEARED': continue
                if a.media_class!='COMMUNITY_CONTEXT' and a.property_id != property_id: continue
                eligible.append(a)
            eligible.sort(key=lambda a:(a.version,a.media_id), reverse=True)
            if len(eligible)>1 and eligible[0].version==eligible[1].version:
                raise MediaBindingError(f'ambiguous approved media for slot {sid}')
            if not eligible:
                if required: raise MediaBindingError(f'required media slot unbound: {sid}')
                out.append(BoundMedia(sid,stype,None,None,'NO_APPROVED_COMPATIBLE_MEDIA'))
                continue
            a=eligible[0]
            dep=PresentationDependency('MEDIA',a.media_id,a.semantic_fingerprint,a.version,sid)
            out.append(BoundMedia(sid,stype,a.media_id,dep,None))
        return tuple(out)
