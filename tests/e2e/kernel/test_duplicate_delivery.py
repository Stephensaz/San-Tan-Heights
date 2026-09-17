from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
def test_event_consumption_has_consumer_event_uniqueness():
 sql=(ROOT/'database/migrations/0074_event_consumptions.sql').read_text()
 assert 'consumer_name' in sql and 'event_id' in sql
 assert 'UNIQUE' in sql.upper() or 'PRIMARY KEY' in sql.upper()
