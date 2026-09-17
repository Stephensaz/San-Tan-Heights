from pathlib import Path
import json, yaml

ROOT=Path(__file__).resolve().parents[2]

def test_all_registered_event_schemas_exist():
    registry=yaml.safe_load((ROOT/'registries/events/events.yaml').read_text())
    for event in registry['events']:
        p=ROOT/'schemas/events'/event['schema_file']
        assert p.is_file(), event['id']
        schema=json.loads(p.read_text())
        assert schema['type']=='object'

def test_all_events_have_at_least_one_producer_and_topic():
    registry=yaml.safe_load((ROOT/'registries/events/events.yaml').read_text())
    for event in registry['events']:
        assert event.get('producers')
        assert event.get('topics')
