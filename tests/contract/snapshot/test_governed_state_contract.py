from pathlib import Path
import json, yaml
ROOT=Path(__file__).resolve().parents[3]
def test_contract_and_schemas_exist():
    c=yaml.safe_load((ROOT/'contracts/services/governed-property-state-read-v1.0.yaml').read_text())
    assert c['status']=='LOCKED' and c['operation']=='GetGovernedPropertyState'
    for n in ['governed-property-state.schema.json','governed-finding-input.schema.json','governed-dependency-input.schema.json']:
        d=json.loads((ROOT/'schemas/snapshots'/n).read_text()); assert d['type']=='object'
