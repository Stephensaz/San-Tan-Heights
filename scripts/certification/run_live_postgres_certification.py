#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from typing import Mapping

ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = ROOT / 'database' / 'migrations'
REQUIRED_CHECKS = (
    'MIGRATIONS_EXECUTED',
    'IMMUTABILITY_TRIGGERS_VERIFIED',
    'LEAST_PRIVILEGE_GRANTS_VERIFIED',
    'LOCKING_AND_CONCURRENCY_VERIFIED',
    'BACKUP_RESTORE_VERIFIED',
)
DB_RE = re.compile(r'^[a-z][a-z0-9_]{2,48}$')


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def evidence_hash(payload: Mapping[str, object]) -> str:
    return sha256(canonical_json(payload).encode('utf-8')).hexdigest()


class CommandFailure(RuntimeError):
    def __init__(self, command: list[str], returncode: int, stdout: str, stderr: str):
        super().__init__(f'command failed ({returncode}): {" ".join(command)}\n{stderr}')
        self.command = command
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def run(cmd: list[str], *, check: bool = True, timeout: int = 120, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    cp = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout, env=env)
    if check and cp.returncode != 0:
        raise CommandFailure(cmd, cp.returncode, cp.stdout, cp.stderr)
    return cp


def psql(db: str, sql: str, *, check: bool = True, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return run(['psql', '-X', '-v', 'ON_ERROR_STOP=1', '-Atq', '-d', db, '-c', sql], check=check, timeout=timeout)


def require_toolchain() -> dict[str, str]:
    tools = {}
    for name in ('psql', 'createdb', 'dropdb', 'pg_dump', 'pg_restore'):
        path = shutil.which(name)
        if not path:
            raise RuntimeError(f'missing required PostgreSQL tool: {name}')
        tools[name] = path
    return tools


def create_db(maintenance_db: str, db: str) -> None:
    psql(maintenance_db, f'CREATE DATABASE {db};')


def drop_db(maintenance_db: str, db: str) -> None:
    psql(maintenance_db, f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='{db}' AND pid<>pg_backend_pid();", check=False)
    psql(maintenance_db, f'DROP DATABASE IF EXISTS {db};', check=False)


def apply_migrations(db: str) -> list[str]:
    applied: list[str] = []
    for migration in sorted(MIGRATIONS.glob('*.sql')):
        cp = run(['psql', '-X', '-v', 'ON_ERROR_STOP=1', '-d', db, '-f', str(migration)], timeout=120)
        applied.append(migration.name)
    return applied


def verify_server_version(db: str) -> str:
    raw = psql(db, "SHOW server_version_num;").stdout.strip()
    try:
        num = int(raw)
    except ValueError as exc:
        raise RuntimeError(f'invalid PostgreSQL server_version_num: {raw!r}') from exc
    if num < 160000:
        raise RuntimeError(f'PostgreSQL 16+ required, observed server_version_num={num}')
    return raw


def seed_ready_fixture(db: str) -> None:
    sql = r"""
INSERT INTO core.properties(property_id,canonical_key) VALUES
('00000000-0000-0000-0000-00000000c001','live-cert-property') ON CONFLICT DO NOTHING;
INSERT INTO snapshot.intelligence_snapshots(
 snapshot_id,property_id,snapshot_sequence,snapshot_reason,governed_state_version,source_read_token,
 intelligence_schema_version,governance_schema_version,model_version,semantic_fingerprint,
 agent_semantic_fingerprint,seller_semantic_fingerprint,public_semantic_fingerprint,snapshot_hash,
 snapshot_completeness_status,qa_status,qa_completed_at,created_by
) VALUES (
 '00000000-0000-0000-0000-00000000c002','00000000-0000-0000-0000-00000000c001',1,'LIVE_CERT','v1','token-1',
 '1.0','1.0','1.0',repeat('a',64),repeat('b',64),repeat('c',64),repeat('d',64),repeat('e',64),
 'COMPLETE','PASS',now(),'live-cert'
) ON CONFLICT DO NOTHING;
INSERT INTO reporting.report_versions(
 report_id,property_id,report_variant,version_number,snapshot_id,report_schema_version,content_contract_version,
 variant_policy_version,builder_version,report_input_hash,canonical_payload_hash,stored_payload_hash,canonical_payload,
 dependency_manifest_hash,generation_reason,content_state,health_state,qa_status,qa_completed_at,publication_eligible,created_by
) VALUES (
 '00000000-0000-0000-0000-00000000c003','00000000-0000-0000-0000-00000000c001','PUBLIC',1,
 '00000000-0000-0000-0000-00000000c002','1.0','1.0','1.0','live-cert',repeat('f',64),repeat('1',64),repeat('1',64),
 '{"title":"cert"}'::jsonb,repeat('2',64),'LIVE_CERT','READY','CLEAN','PASS',now(),true,'live-cert'
) ON CONFLICT DO NOTHING;
INSERT INTO reporting.render_versions(
 render_id,report_id,render_type,render_version,render_contract_version,template_id,template_version,renderer_version,
 presentation_input_hash,artifact_hash,artifact_size_bytes,storage_uri,mime_type,content_state,health_state,qa_status,
 qa_completed_at,publication_eligible,created_by
) VALUES (
 '00000000-0000-0000-0000-00000000c004','00000000-0000-0000-0000-00000000c003','WEB',1,'1.0','cert','1.0','live-cert',
 repeat('3',64),repeat('4',64),4,'memory://cert','text/html','READY','CLEAN','PASS',now(),true,'live-cert'
) ON CONFLICT DO NOTHING;
"""
    psql(db, sql)


def expect_failure(db: str, sql: str, marker: str) -> None:
    cp = psql(db, sql, check=False)
    text = f'{cp.stdout}\n{cp.stderr}'
    if cp.returncode == 0 or marker not in text:
        raise RuntimeError(f'expected failure marker {marker!r}, got rc={cp.returncode}: {text}')


def check_immutability(db: str) -> dict[str, object]:
    seed_ready_fixture(db)
    expect_failure(
        db,
        "UPDATE reporting.report_versions SET canonical_payload='{}'::jsonb WHERE report_id='00000000-0000-0000-0000-00000000c003';",
        'READY_REPORT_SEMANTICS_IMMUTABLE',
    )
    expect_failure(
        db,
        "UPDATE reporting.render_versions SET artifact_hash=repeat('9',64) WHERE render_id='00000000-0000-0000-0000-00000000c004';",
        'READY_RENDER_ARTIFACT_IMMUTABLE',
    )
    return {'report_trigger': 'PASS', 'render_trigger': 'PASS'}


def check_least_privilege(db: str) -> dict[str, object]:
    allowed = psql(db, "SET ROLE sth_public_delivery; SELECT count(*) FROM publication.current_public_reports;")
    denied = psql(db, "SET ROLE sth_public_delivery; SELECT count(*) FROM reporting.report_versions;", check=False)
    if denied.returncode == 0 or 'permission denied' not in denied.stderr.lower():
        raise RuntimeError('sth_public_delivery unexpectedly read reporting.report_versions')
    write_denied = psql(db, "SET ROLE sth_public_delivery; DELETE FROM publication.report_current;", check=False)
    if write_denied.returncode == 0 or 'permission denied' not in write_denied.stderr.lower():
        raise RuntimeError('sth_public_delivery unexpectedly mutated publication.report_current')
    return {'public_projection_read': 'PASS', 'base_table_read_denied': 'PASS', 'pointer_write_denied': 'PASS'}


def check_locking(db: str) -> dict[str, object]:
    psql(db, """
INSERT INTO reporting.report_version_counters(property_id,report_variant,next_version)
VALUES ('00000000-0000-0000-0000-00000000c001','PUBLIC',1)
ON CONFLICT(property_id,report_variant) DO UPDATE SET next_version=1;
""")
    a_sql = """
BEGIN;
SELECT next_version FROM reporting.report_version_counters
WHERE property_id='00000000-0000-0000-0000-00000000c001' AND report_variant='PUBLIC' FOR UPDATE;
SELECT pg_sleep(2);
UPDATE reporting.report_version_counters SET next_version=next_version+1
WHERE property_id='00000000-0000-0000-0000-00000000c001' AND report_variant='PUBLIC';
COMMIT;
"""
    b_sql = """
BEGIN;
SELECT next_version FROM reporting.report_version_counters
WHERE property_id='00000000-0000-0000-0000-00000000c001' AND report_variant='PUBLIC' FOR UPDATE;
UPDATE reporting.report_version_counters SET next_version=next_version+1
WHERE property_id='00000000-0000-0000-0000-00000000c001' AND report_variant='PUBLIC';
COMMIT;
"""
    a = subprocess.Popen(['psql','-X','-v','ON_ERROR_STOP=1','-Atq','-d',db,'-c',a_sql], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(0.35)
    start_b = time.monotonic()
    b = run(['psql','-X','-v','ON_ERROR_STOP=1','-Atq','-d',db,'-c',b_sql], timeout=30)
    elapsed_b = time.monotonic() - start_b
    a_out, a_err = a.communicate(timeout=30)
    if a.returncode != 0:
        raise RuntimeError(f'locking session A failed: {a_err}')
    final = int(psql(db, "SELECT next_version FROM reporting.report_version_counters WHERE property_id='00000000-0000-0000-0000-00000000c001' AND report_variant='PUBLIC';").stdout.strip())
    if final != 3:
        raise RuntimeError(f'expected next_version=3 after serialized increments, observed {final}')
    if elapsed_b < 1.0:
        raise RuntimeError(f'session B did not visibly wait on row lock (elapsed={elapsed_b:.3f}s)')
    return {'serialized_counter_value': final, 'second_session_wait_seconds': round(elapsed_b, 3)}


def check_backup_restore(db: str, restore_db: str, maintenance_db: str) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix='sth-pg-cert-') as td:
        dump = Path(td) / 'cert.dump'
        run(['pg_dump', '-Fc', '--no-owner', '--no-privileges', '-d', db, '-f', str(dump)], timeout=120)
        if not dump.exists() or dump.stat().st_size <= 0:
            raise RuntimeError('pg_dump did not produce a non-empty artifact')
        create_db(maintenance_db, restore_db)
        run(['pg_restore', '--no-owner', '--no-privileges', '-d', restore_db, str(dump)], timeout=180)
        property_count = int(psql(restore_db, "SELECT count(*) FROM core.properties WHERE property_id='00000000-0000-0000-0000-00000000c001';").stdout.strip())
        trigger_count = int(psql(restore_db, "SELECT count(*) FROM pg_trigger WHERE tgname IN ('trg_ready_report_semantics_immutable','trg_ready_render_artifact_immutable') AND NOT tgisinternal;").stdout.strip())
        if property_count != 1:
            raise RuntimeError('restored fixture property missing')
        if trigger_count != 2:
            raise RuntimeError(f'restored immutability triggers incomplete: {trigger_count}/2')
        return {'dump_size_bytes': dump.stat().st_size, 'restored_property': 'PASS', 'restored_immutability_triggers': trigger_count}


def main() -> int:
    ap = argparse.ArgumentParser(description='Execute the STH M7-027 live PostgreSQL 16+ certification battery.')
    ap.add_argument('--candidate-fingerprint', required=True, help='Exact frozen M7 candidate SHA-256 fingerprint.')
    ap.add_argument('--source-revision', required=True, help='Source revision corresponding to the frozen candidate.')
    ap.add_argument('--maintenance-db', default=os.environ.get('PGMAINTENANCE_DB', 'postgres'))
    ap.add_argument('--work-db', default='sth_m7_cert')
    ap.add_argument('--restore-db', default='sth_m7_cert_restore')
    ap.add_argument('--evidence-out', default=str(ROOT / 'artifacts' / 'certification' / 'live-postgres-evidence.json'))
    ap.add_argument('--keep-databases', action='store_true')
    args = ap.parse_args()
    if not re.fullmatch(r'[0-9a-f]{64}', args.candidate_fingerprint):
        ap.error('--candidate-fingerprint must be lowercase SHA-256')
    if not args.source_revision.strip():
        ap.error('--source-revision is required')
    for value in (args.work_db, args.restore_db):
        if not DB_RE.fullmatch(value):
            ap.error(f'invalid certification database name: {value!r}')

    statuses = {code: 'NOT_RUN' for code in REQUIRED_CHECKS}
    details: dict[str, object] = {}
    available = False
    executed = False
    work_created = False
    restore_created = False
    try:
        details['toolchain'] = require_toolchain()
        available = True
        drop_db(args.maintenance_db, args.restore_db)
        drop_db(args.maintenance_db, args.work_db)
        create_db(args.maintenance_db, args.work_db)
        work_created = True
        details['server_version_num'] = verify_server_version(args.work_db)
        details['migrations'] = apply_migrations(args.work_db)
        statuses['MIGRATIONS_EXECUTED'] = 'PASS'
        executed = True

        details['immutability'] = check_immutability(args.work_db)
        statuses['IMMUTABILITY_TRIGGERS_VERIFIED'] = 'PASS'

        details['least_privilege'] = check_least_privilege(args.work_db)
        statuses['LEAST_PRIVILEGE_GRANTS_VERIFIED'] = 'PASS'

        details['locking'] = check_locking(args.work_db)
        statuses['LOCKING_AND_CONCURRENCY_VERIFIED'] = 'PASS'

        details['backup_restore'] = check_backup_restore(args.work_db, args.restore_db, args.maintenance_db)
        restore_created = True
        statuses['BACKUP_RESTORE_VERIFIED'] = 'PASS'
    except Exception as exc:
        details['error'] = f'{type(exc).__name__}: {exc}'
        executed = executed or available
        first_not_pass = next((c for c in REQUIRED_CHECKS if statuses[c] != 'PASS'), None)
        if first_not_pass:
            statuses[first_not_pass] = 'FAIL'
    finally:
        if not args.keep_databases:
            if restore_created or available:
                drop_db(args.maintenance_db, args.restore_db)
            if work_created or available:
                drop_db(args.maintenance_db, args.work_db)

    payload = {
        'schema_version': '1.1.0',
        'candidate_fingerprint': args.candidate_fingerprint,
        'source_revision': args.source_revision,
        'available': available,
        'executed': executed,
        'check_statuses': statuses,
        'detail': details,
    }
    payload['evidence_fingerprint'] = evidence_hash(payload)
    out = Path(args.evidence_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n')
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if all(statuses[c] == 'PASS' for c in REQUIRED_CHECKS) else 2


if __name__ == '__main__':
    raise SystemExit(main())
