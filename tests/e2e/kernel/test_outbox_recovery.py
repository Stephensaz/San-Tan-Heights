from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
def test_outbox_claim_contract_supports_skip_locked_and_leases():
 sql=(ROOT/'database/migrations/0072_outbox.sql').read_text()
 worker=(ROOT/'workers/outbox_dispatcher/worker.py').read_text()
 assert 'lease_expires_at' in sql
 assert 'SKIP LOCKED' in (ROOT/'src/kernel/outbox/repository.py').read_text()
 assert 'reclaim' in worker.lower() or 'lease' in worker.lower()
