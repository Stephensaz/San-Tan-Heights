from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable
from src.renderer.contracts import RenderContractRegistry
from src.renderer.hashing import PresentationDependency, PresentationInputHashEngine, PresentationInputIdentity
from src.renderer.media import MediaAsset, MediaSlotBinder, BoundMedia
from src.renderer.diagrams import DiagramAsset, DiagramSlotBinder, BoundDiagram

class RenderRequestError(ValueError): pass

@dataclass(frozen=True)
class PresentationProfile:
    template_id: str
    template_version: str
    template_fingerprint: str
    brand_profile_id: str
    brand_version: str
    brand_fingerprint: str
    renderer_version: str

@dataclass(frozen=True)
class RenderRequest:
    report_id: str
    property_id: str
    render_type: str
    presentation_input_hash: str
    render_contract_version: str
    profile: PresentationProfile
    media: tuple[BoundMedia,...]
    diagrams: tuple[BoundDiagram,...]
    dependencies: tuple[PresentationDependency,...]

class RenderRequestService:
    def __init__(self, *, contracts, media_binder, diagram_binder, hasher=None):
        self.contracts=contracts; self.media_binder=media_binder; self.diagram_binder=diagram_binder; self.hasher=hasher or PresentationInputHashEngine()
    @staticmethod
    def _dep(kind, ident, fp, ver): return PresentationDependency(kind,ident,fp,ver,None)
    def build(self, *, report_id: str, property_id: str, render_type: str, canonical_payload_hash: str, report_input_hash: str, media_slots, diagram_slots, media_assets: Iterable[MediaAsset], diagram_assets: Iterable[DiagramAsset], profile: PresentationProfile) -> RenderRequest:
        contract=self.contracts.resolve(render_type)
        media=self.media_binder.bind(property_id=property_id, slots=media_slots, assets=media_assets)
        diagrams=self.diagram_binder.bind(property_id=property_id, slots=diagram_slots, assets=diagram_assets)
        deps=[
            self._dep('TEMPLATE',profile.template_id,profile.template_fingerprint,profile.template_version),
            self._dep('BRANDING',profile.brand_profile_id,profile.brand_fingerprint,profile.brand_version),
        ]
        deps += [x.dependency for x in media if x.dependency]
        deps += [x.dependency for x in diagrams if x.dependency]
        identity=self.hasher.calculate(report_id=report_id,render_type=render_type,canonical_report_payload_hash=canonical_payload_hash,report_input_hash=report_input_hash,render_contract_version=contract.render_contract_version,template_id=profile.template_id,template_version=profile.template_version,renderer_version=profile.renderer_version,dependencies=deps)
        return RenderRequest(report_id,property_id,render_type,identity.presentation_input_hash,contract.render_contract_version,profile,media,diagrams,tuple(deps))
