from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[2]
def test_m4_controlled_publication_contract_surface_is_complete():
    expected=[
      'src/publication/history/service.py','src/publication/lifecycle/service.py','src/publication/freeze/repository.py',
      'src/publication/routing/resolver.py','src/publication/cache/events.py','database/migrations/0048_publication_lifecycle.sql'
    ]
    assert all((ROOT/x).exists() for x in expected)

def test_m4_routing_has_all_delivery_channels():
    d=yaml.safe_load((ROOT/'registries/publication/delivery-routing.yaml').read_text())
    assert set(d['routes'])=={'WEB','PDF_DOWNLOAD','PRINT'}
    assert all('{property_id}' in x['path_template'] and '{variant}' in x['path_template'] for x in d['routes'].values())

def test_m4_publication_history_remains_append_only():
    s=(ROOT/'database/migrations/0046_publication_history_immutability.sql').read_text()
    assert 'BEFORE UPDATE OR DELETE ON publication.publication_history' in s
