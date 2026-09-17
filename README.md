# San Tan Heights Intelligence

Production implementation repository for the governed San Tan Heights Property Intelligence platform.

## Governing rule
Implementation follows the locked San Tan Heights Master Build Specification. Code implements certified contracts; it does not redesign them.

## Build order
1. Milestone 1 — Governed Lifecycle Kernel
2. Milestone 2 — Intelligence Bridge
3. Milestone 3 — Report Production
4. Milestone 4 — Rendering & Controlled Publication
5. Milestone 5 — Fleet Control & Operations
6. Milestone 6 — Security & System Certification
7. Milestone 7 — Production Certification & Go-Live
8. Milestone 8 — Consumer Experience

A downstream milestone must not be accepted before its required upstream milestones are ACCEPTED.

## Architecture change control
Any implementation change that alters governed meaning, state transitions, publication behavior, audience visibility, security, historical reproducibility, or lifecycle invariants requires an Architecture Change Request before code changes.

## Migration rules
- PostgreSQL 16+
- Never reuse migration numbers.
- Never edit an already-applied migration.
- No destructive cascade deletes in normal runtime paths.
- Workflow states use reference tables rather than native database ENUMs.

## Status values
- NOT_STARTED
- IN_PROGRESS
- BLOCKED
- ACCEPTED

## Current engineering start point
M1-001 Repository Bootstrap — IN_PROGRESS
