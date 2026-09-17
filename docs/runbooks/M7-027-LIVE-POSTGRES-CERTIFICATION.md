# M7-027 Live PostgreSQL 16+ Certification Runbook

## Purpose
Execute the five live database checks required by `STH-M7-FINAL-CERTIFICATION-POLICY` against an isolated PostgreSQL 16+ certification instance. Structural/static SQL tests are not a substitute for this run.

Required checks:

1. `MIGRATIONS_EXECUTED`
2. `IMMUTABILITY_TRIGGERS_VERIFIED`
3. `LEAST_PRIVILEGE_GRANTS_VERIFIED`
4. `LOCKING_AND_CONCURRENCY_VERIFIED`
5. `BACKUP_RESTORE_VERIFIED`

## Required toolchain

The certification host must provide compatible versions of:

- `psql`
- `createdb`
- `dropdb`
- `pg_dump`
- `pg_restore`
- PostgreSQL server 16 or newer

The database user must be able to create/drop isolated certification databases and create the NOLOGIN roles defined by the migrations. Use a disposable certification PostgreSQL instance, not the live production database.

## Connection

The harness uses standard libpq environment variables. Example:

```bash
export PGHOST=127.0.0.1
export PGPORT=5432
export PGUSER=postgres
export PGPASSWORD='<certification-only-password>'
export PGMAINTENANCE_DB=postgres
```

Do not commit credentials or place them in the evidence bundle.

## Run

From the repository root:

```bash
python scripts/certification/run_live_postgres_certification.py \
  --work-db sth_m7_cert \
  --restore-db sth_m7_cert_restore \
  --evidence-out artifacts/certification/live-postgres-evidence.json
```

The harness creates isolated databases, applies every SQL migration with `ON_ERROR_STOP=1`, runs the certification battery, writes machine-readable evidence, and drops the databases unless `--keep-databases` is specified.

A successful run exits `0`. Any failed or incomplete live check exits nonzero.

## What the harness proves

### Migration execution
- PostgreSQL server is version 16+.
- Every file in `database/migrations/*.sql` executes successfully in deterministic filename order.

### Immutability
- A READY semantic report rejects mutation of its canonical payload.
- A READY render rejects mutation of its artifact hash.
- The expected database trigger error markers are observed from the live server.

### Least privilege
- `sth_public_delivery` can read the sanitized current-Public projection.
- `sth_public_delivery` cannot read `reporting.report_versions` directly.
- `sth_public_delivery` cannot mutate publication pointers.

### Locking/concurrency
- Two independent PostgreSQL sessions contend for the same report-version-counter row.
- The second session waits for the first row lock.
- Both increments serialize and the final counter value is exact.

### Backup/restore
- `pg_dump` produces a non-empty custom-format backup.
- The backup restores into a separate database.
- The known certification fixture survives restore.
- READY report/render immutability triggers survive restore.

## Evidence integrity

The JSON output contains:

- `available`
- `executed`
- `check_statuses`
- per-check details
- `evidence_fingerprint`

The fingerprint is SHA-256 over the canonical evidence payload. `load_live_postgresql_evidence()` rejects edited/tampered evidence.

## Final M7 gate

Only after all five live checks are `PASS` should the evidence file be supplied to the M7-027 final certification evaluation. M7 remains `BLOCKED / NO_GO` for missing, partial, tampered, or failed live PostgreSQL evidence.

## Disposable GitHub Actions execution

The repository includes `.github/workflows/m7-live-postgres-certification.yml` for a disposable PostgreSQL 16 certification environment.

From a GitHub-hosted copy of this repository, run **M7 Live PostgreSQL Certification** with `workflow_dispatch` (or allow it to run automatically when the workflow's guarded paths change). The job provisions `postgres:16`, executes the same harness documented above, verifies the evidence fingerprint, verifies all five required checks are PASS, and uploads the JSON evidence artifact named `m7-live-postgres-certification-evidence`.

A green workflow is live-database evidence; merely having the workflow file in the repository is not. Download the produced `live-postgres-evidence.json` and supply that exact file to the M7-027 final certification evaluation.
