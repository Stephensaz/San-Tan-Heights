from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import yaml

@dataclass(frozen=True)
class DeliveryRoute:
    channel:str; path:str; report_id:object; render_id:object; pointer_version:int

class StableDeliveryRouter:
    def __init__(self,publication_repository,registry_path=None):
        self.repository=publication_repository
        p=Path(registry_path) if registry_path else Path(__file__).resolve().parents[3]/'registries/publication/delivery-routing.yaml'
        self.registry=yaml.safe_load(p.read_text())
    def resolve(self,cursor,*,property_id,report_variant,channel):
        cfg=self.registry['routes'].get(channel)
        if not cfg: raise ValueError('unsupported publication channel')
        current=self.repository.get_channel_pointer(cursor,property_id,report_variant,channel)
        if current is None: return None
        report_id,render_id,pointer_version=current
        path=cfg['path_template'].format(property_id=property_id,variant=report_variant.lower())
        return DeliveryRoute(channel,path,report_id,render_id,pointer_version)
