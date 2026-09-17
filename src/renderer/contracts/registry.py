from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import yaml


class RenderContractRegistryError(ValueError):
    pass


@dataclass(frozen=True)
class RenderContract:
    render_type: str
    render_contract_version: str
    artifact_kind: str
    mime_types: tuple[str, ...]
    publication_channels: tuple[str, ...]
    required_inputs: tuple[str, ...]
    forbidden_semantic_behavior: tuple[str, ...]


@dataclass(frozen=True)
class RenderContractRegistry:
    registry_id: str
    version: str
    contracts: dict[str, RenderContract]

    EXPECTED_TYPES = frozenset({'WEB', 'PDF', 'PRINT', 'MOBILE_PREVIEW'})
    REQUIRED_INPUTS = frozenset({
        'canonical_report_payload_hash', 'report_input_hash', 'template_id',
        'template_version', 'renderer_version', 'render_dependency_manifest',
    })

    @classmethod
    def from_repository(cls, root: Path) -> 'RenderContractRegistry':
        path = root / 'registries/render-contracts/render-contracts-v1.0.yaml'
        raw = yaml.safe_load(path.read_text()) or {}
        if raw.get('registry_id') != 'STH-RENDER-CONTRACTS-v1.0':
            raise RenderContractRegistryError('unexpected render contract registry id')
        if str(raw.get('version')) != '1.0.0':
            raise RenderContractRegistryError('unexpected render contract registry version')
        items = raw.get('contracts') or {}
        if set(items) != cls.EXPECTED_TYPES:
            raise RenderContractRegistryError('render contract types must be exact')
        contracts = {}
        for render_type, item in items.items():
            required_inputs = tuple(item.get('required_inputs') or ())
            if set(required_inputs) != cls.REQUIRED_INPUTS:
                raise RenderContractRegistryError(f'{render_type} required inputs must be exact')
            forbidden = tuple(item.get('forbidden_semantic_behavior') or ())
            if not forbidden:
                raise RenderContractRegistryError(f'{render_type} must define forbidden semantic behavior')
            mime_types = tuple(item.get('mime_types') or ())
            if not mime_types:
                raise RenderContractRegistryError(f'{render_type} must define mime type')
            contracts[render_type] = RenderContract(
                render_type=render_type,
                render_contract_version=str(item['render_contract_version']),
                artifact_kind=str(item['artifact_kind']),
                mime_types=mime_types,
                publication_channels=tuple(item.get('publication_channels') or ()),
                required_inputs=required_inputs,
                forbidden_semantic_behavior=forbidden,
            )
        return cls(str(raw['registry_id']), str(raw['version']), contracts)

    def resolve(self, render_type: str) -> RenderContract:
        try:
            return self.contracts[render_type]
        except KeyError as exc:
            raise RenderContractRegistryError(f'unsupported render type: {render_type}') from exc
