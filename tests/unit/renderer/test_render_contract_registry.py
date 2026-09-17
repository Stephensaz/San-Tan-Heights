from pathlib import Path
import pytest
from src.renderer.contracts import RenderContractRegistry, RenderContractRegistryError
ROOT=Path(__file__).resolve().parents[3]

def test_registry_loads_all_supported_render_types():
    r=RenderContractRegistry.from_repository(ROOT)
    assert set(r.contracts)=={'WEB','PDF','PRINT','MOBILE_PREVIEW'}
    assert r.resolve('PDF').mime_types == ('application/pdf',)
    assert r.resolve('WEB').publication_channels == ('WEB',)

def test_every_contract_forbids_semantic_invention():
    r=RenderContractRegistry.from_repository(ROOT)
    for c in r.contracts.values():
        assert 'create_new_property_fact' in c.forbidden_semantic_behavior
        assert 'reinterpret_governed_finding' in c.forbidden_semantic_behavior

def test_unknown_type_fails_closed():
    r=RenderContractRegistry.from_repository(ROOT)
    with pytest.raises(RenderContractRegistryError): r.resolve('EMAIL')
