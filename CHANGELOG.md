## 0.1.54 — GitHub bootstrap lease guard

- Added a one-time SHA-pinned `--force-with-lease` bootstrap path for replacing only the known connector-created GitHub bootstrap commit.
- The bootstrap script verifies the remote branch still equals the supplied bootstrap SHA before any history replacement; intervening remote changes fail closed.
- General force-push flags remain prohibited.
- M7-027 remains BLOCKED pending executed candidate-bound PostgreSQL 16+ certification evidence.

## 0.1.52 — M7-027 Automatic Git Candidate Binding

- Added deterministic candidate freezing from the exact committed Git revision/tree and locked architecture/build/contract inputs.
- The live PostgreSQL workflow now derives the candidate fingerprint automatically instead of requiring a manually supplied production hash.
- Added optional expected-fingerprint verification and uploads the immutable candidate-binding artifact alongside PostgreSQL evidence.
- Fixed the M7 finalizer version-transition test to compute the next patch version rather than hardcoding a release number.
- GitHub integration is installed for the Stephensaz account but currently exposes zero repositories; M7-027 therefore remains BLOCKED until a repository exists and the live workflow executes.
- Full repository suite: 565 tests passed; repository validation PASS.

## 0.1.51 — M7-027 Candidate-Bound Evidence Finalization

- Bound live PostgreSQL certification evidence to the exact frozen M7 candidate fingerprint and source revision.
- M7-027 now hard-fails executed live evidence from a different candidate while unavailable/unexecuted evidence remains BLOCKED.
- Added `finalize_m7_from_live_evidence.py`, which validates the tamper-evident artifact and can apply the guarded M7 ACCEPTED -> M8 IN_PROGRESS repository transition only after all five live PostgreSQL checks pass.
- Added atomic repository finalization logic and tests using a temporary repository copy; no status mutation occurs for invalid evidence.
- M7-027 remains BLOCKED until an actual candidate-bound PostgreSQL 16+ workflow run produces all-PASS evidence.
- Full repository suite: 562 tests passed; repository validation PASS.

## 0.1.50 — M7-027 Disposable PostgreSQL 16 CI Harness

- Added a GitHub Actions production-certification workflow backed by an isolated PostgreSQL 16 service container.
- The workflow runs the live M7-027 database battery, independently verifies the tamper-evident evidence and all five required PASS checks, and uploads the evidence artifact on success or failure.
- Added workflow contract tests and documented the one-click disposable execution path.
- M7-027 remains BLOCKED until a real workflow/host execution produces verified all-PASS live PostgreSQL evidence.
- Full repository suite: 558 tests passed; repository validation PASS.

## 0.1.49 — M7-027 live PostgreSQL certification harness

- Kept M7-027 and Milestone 7 BLOCKED because this sandbox cannot provision or execute PostgreSQL 16+.
- Added a self-contained live PostgreSQL certification harness covering migration execution, READY report/render immutability, least-privilege grants, two-session row-lock serialization, and real pg_dump/pg_restore verification.
- Added tamper-evident live PostgreSQL evidence loading for the M7-027 final gate.
- Added the exact external certification runbook.
- Corrected a live-migration defect in `0143_least_privilege_completion.sql`: `r.report_version` -> `r.version_number AS report_version`.
- Full repository suite: 555 tests passed; repository validation PASS.

## 0.1.46 — M7-020 through M7-022
- Accepted Manual Publication Policy with manual-by-default pointer mutation, operator/reason evidence, exact candidate matching, and fresh CLEAR stop-condition gating.
- Accepted Progressive Automation Policy with explicit stage handoffs bound to the immediate prior PASS certification, candidate fingerprint, stop-condition evidence, requester, and reason.
- Accepted Rollback Baseline Capture with deterministic, complete pre-automation semantic/channel pointer snapshots for every target property.
- Added immutable PostgreSQL persistence for automation handoffs, rollback baselines, and baseline entries.
- Full repository suite: 540 tests passing; repository validation PASS.
- Advanced current implementation ticket to M7-023 Cohort Rollback / Containment.

## 0.1.45 — M7-017 through M7-019
- Added locked progressive rollout policy for Cohort 100, Cohort 500, and Remaining Fleet stages.
- Added deterministic disjoint membership freezing against the broader currently eligible fleet.
- Required PASS certification of the immediately prior cohort and fresh go-live stop-condition clearance before each expansion.
- Added fail-fast progressive deployment and immutable cohort certification evidence.
- Added append-only PostgreSQL persistence for progressive cohort membership, deployments, items, and certifications.
- Certified the 4,956-property expansion chain as 25 + 100 + 500 + 4,331 remaining properties with no overlap.
- Advanced current implementation ticket to M7-020 Manual Publication Policy.

## 0.1.39 — M7-001 Production Certification Persistence Completion

- Accepted M7-001 Production Certification Persistence Completion.
- Added durable `certification.production_runs` anchored to an exact M6 system-certification run and candidate fingerprint.
- Added append-only production evidence and generic production check-result persistence with immutable database triggers.
- Kept candidate freezing, manifest pinning, environment/configuration validation, shadow operation, approvals, cohorts, rollout, rollback, revocation, and FULL_APPROVAL semantics outside M7-001.
- Full repository suite: 481 tests passed; repository validation PASS.
- Advanced current engineering ticket to M7-002 Certification Candidate Freeze.

## 0.1.38 — Milestone 6 Security & System Certification Accepted

- Accepted M6-013 through M6-035 and completed Milestone 6.
- Added time-bounded incident/reason/action-scoped break-glass controls with no delegation path.
- Added locked security-event taxonomy plus durable security audit persistence.
- Added durable production-certification evidence tables with append-only scenario and metric results.
- Added deterministic 4,956-property synthetic fleet generation, golden fixtures, locked scenario registry, deterministic chaos harness, and reproducibility checks.
- Added certification suites for normal lifecycle, idempotency, variant isolation, stale builds, publication races, rollback/invalidation, releases, recovery, security mutation, leakage, chaos, and disaster recovery.
- Added locked hard-zero safety metrics and a certification runner that emits GO only when all scenarios pass and every hard-zero metric is zero; there is no waiver path.
- Full repository suite: 473 tests passed; repository validation PASS.
- Milestone 6 Security & System Certification is ACCEPTED; M7-001 Production Certification Persistence Completion is now IN_PROGRESS.

## 0.1.36 — M6-007 through M6-009 Audience Data-Exposure Boundary

- Accepted M6-007 Audience Enforcement with a locked fail-closed audience registry separating report-variant access from property authorization.
- Accepted M6-008 Response DTO Segregation with physically distinct Public, Seller, and Agent immutable response types built by explicit whitelist projection.
- Accepted M6-009 Negative-Field Protection with recursive audience-specific forbidden-field checks as defense in depth.
- Public responses exclude lineage, fingerprints, evidence internals, and schema/policy internals; Seller responses exclude snapshot/fingerprint lineage and evidence detail; Agent responses still reject restricted/system-secret fields.
- Full repository suite: 438 tests passed; repository validation PASS.
- Advanced current engineering ticket to M6-010 Private Media Authorization.

## 0.1.33 — Milestone 5 certification

- Accepted M5-027 Backup Verification through M5-031 Milestone 5 Certification Suite.
- Added durable backup and restore verification evidence with fail-closed hash, size, manifest, integrity, and row-count checks.
- Added mandatory global post-restore publication freeze and integrated it into the existing publication freeze guard path.
- Added read-only operations dashboard projection for fleet, incident, release, backup, restore, and global-freeze status.
- Added additive governed reason codes for backup/restore/freeze operations.
- Milestone 5 Fleet Control and Operations is ACCEPTED; M6-001 is now IN_PROGRESS.
- Full repository suite: 411 tests passed; repository validation PASS.

## 0.1.31 — M5-015 through M5-022 Operations Health & Integrity Monitoring

- Accepted fleet and property health models with deterministic severity aggregation.
- Added derived operations read models over authoritative snapshot/job/release state.
- Added STH-RECONCILIATION-RULES-v1.0 with fail-closed integrity-rule lookup.
- Added publication-pointer, orphan, stuck-job, and release-integrity sweep engines.
- Added append-only integrity sweep run/finding persistence for durable operational evidence.
- Full repository validation: 390 tests passed; repository validation PASS.
- Advanced current engineering ticket to M5-023 Incident Persistence & Lifecycle.

## 0.1.28 — M5-001

## 0.1.30 — M5-005 through M5-014

- Added governed release item and parent lifecycle transition services with append-only item history.
- Added bulk generation coordination without mutation of frozen membership/target evidence.
- Added durable release validation results and manifest-bound approval evidence.
- Added staged approval gates, deterministic chunked publication, and strict partial-failure policy evaluation.
- Added exact-count release reconciliation, reverse-order rollback, and cancellation safeguards requiring rollback after publication activity.
- Registered release execution reason codes through an additive reference seed migration.
- Full repository validation: 379 tests passed.

- Accepted M5-001 Release Persistence Completion.
- Added durable release parent, frozen-manifest storage, and release-item target persistence in the operations schema.
- Preserved exact snapshot/report/render lineage slots and deterministic release membership ordinals without defining later release-policy or lifecycle semantics.
- Added fail-closed repository validation and persistence tests.
- Full repository suite: 359 tests passed; repository validation PASS.
- Advanced current implementation ticket to M5-002 Release Policy Registry.

## 0.1.26 — M4-018 through M4-021 Controlled Publication Core

- Accepted M4-018 Publication Staging with durable idempotent target records and compare-and-set state transitions.
- Accepted M4-019 Publication Guard Engine with fail-closed report/render/channel/eligibility checks.
- Accepted M4-020 Pre-Publication Variant Freshness using the audience-specific snapshot semantic fingerprint immediately before publication.
- Accepted M4-021 Atomic Publication Service with transaction-scoped target serialization, semantic-current and channel-pointer swaps, and append-only publication history.
- Guard or freshness failure leaves existing current publication pointers untouched; database failure propagates for caller rollback.
- Full repository suite: 334 tests passed; repository validation PASS.
- Advanced current engineering ticket to M4-022 Supersession & Publication History.

## 0.1.21 — M4-001 Render Persistence Completion

- Accepted M4-001 Render Persistence Completion.
- Added `reporting.render_versions` anchored exclusively to immutable semantic `report_id` inputs.
- Added presentation-input identity, renderer/template/contract version fields, artifact integrity/storage metadata, lifecycle/QA fields, and render supersession lineage.
- Added `reporting.render_dependencies` plus reverse-dependency indexes for exact presentation dependency lineage.
- Kept version allocation, render-contract policy, media/diagram binding, adapters, and publication authority outside M4-001.
- Full repository suite: 273 tests passed; repository validation PASS.
- Advanced current engineering ticket to M4-002 Render Version Counters.

## 0.1.20 — M3-024 through M3-027 / Milestone 3 Accepted

- Added database-enforced READY semantic immutability while preserving operational lifecycle transitions.
- Added deterministic report semantic diffing and report-diff persistence.
- Integrated the regeneration worker across freshness, delegated build/persist, validation, retry/block, NO_OP, and success paths without publication authority.
- Added Milestone 3 certification coverage; full suite: 263 tests passed.
- Milestone 3 (Report Production) is ACCEPTED; M4-001 is now IN_PROGRESS.

# Changelog

## 0.1.19 — M3-020 through M3-023

- Added exact canonical payload hashing after schema validation.
- Added semantic report deduplication based on report input identity rather than snapshot/render identity.
- Added transaction-scoped report target locking plus concurrency-safe version allocation and immutable persistence.
- Corrected report dependency persistence so configuration dependencies may have no source snapshot while property intelligence dependencies retain lineage.
- Added fail-closed report validation for identity, lineage, hash integrity, and publication eligibility state.
- Full suite: 255 passed; repository validation PASS.

## 0.1.18 — M3-017 through M3-019

- Accepted M3-017 Report Dependency Manifest Builder.
- Accepted M3-018 Report Input Hash Engine.
- Accepted M3-019 Canonical Payload Builder.
- Added consumed-only semantic dependency manifests with deterministic hashing.
- Added semantic report-input hashing that excludes operational/render metadata.
- Added renderer-neutral canonical payload assembly that requires governed summary, section-title, disclaimer, wording, label, and glossary inputs.
- Full repository validation: 242 tests passed.

## 0.1.14 — M3 regeneration coordination runtime
- Accepted M3-004 Regeneration Queue Service with idempotent queueing, current-snapshot targeting, active-target reuse, registry-driven priority, deterministic job keys, and REGENERATION_JOB_QUEUED events.
- Accepted M3-005 Worker Claim / Lease / Heartbeat with priority-ordered `FOR UPDATE SKIP LOCKED` claiming, worker-owned leases, RUNNING promotion, and heartbeat renewal.
- Accepted M3-006 Retry Classification & Recovery with fail-closed classification, bounded exponential retry, BLOCK for deterministic failures, and FAILED on retry exhaustion.
- Added additive event-type seed migration for REGENERATION_JOB_QUEUED and retry/lease-ready indexes without modifying accepted migrations.
- Full repository suite: 187 tests passed; repository validation PASS.
- Advanced current implementation ticket to M3-007 Variant-Specific Job Freshness.

## 0.1.10
- Accepted M2-012 Snapshot Diff Engine.
- Accepted M2-013 Current Snapshot Read Model.
- Accepted M2-014 Dependency Impact Rule Registry.
- Restored SHA-256 pinning and canonical-serialization entry in CONTRACT-MANIFEST after full-suite validation detected packaging drift.
- Advanced current engineering ticket to M2-015 Dependency Reverse Lookup.

## 0.1.9 — Milestone 2 snapshot assembly core

- Accepted M2-009 Snapshot Deduplication with valid semantic-equivalent snapshot reuse.
- Accepted M2-010 Dependency Manifest Builder with registry validation, deterministic normalization, and conflicting-duplicate rejection.
- Accepted M2-011 Snapshot Creation Service with requirement evaluation, finding freeze, Passport verification, independent finding fingerprint verification, dependency manifest construction, overall/variant fingerprints, source-read-token recheck, concurrency-safe snapshot sequence allocation, immutable snapshot persistence, and equivalent-snapshot NO_OP behavior.
- Added `snapshot.snapshot_sequence_counters` instead of unsafe `MAX(sequence)+1` allocation.
- Full repository suite: 128 tests passed; repository structure validation PASS.


## 0.1.8 — M2-006 through M2-008
- Accepted M2-006 Passport Reference Capture with exact immutable Passport version resolution, PASS-QA enforcement, finding/evidence-set matching, and fail-closed lineage validation.
- Accepted M2-007 Finding Fingerprint Engine with independent canonical fingerprint recomputation and `UPSTREAM_FINDING_FINGERPRINT_MISMATCH` detection.
- Accepted M2-008 Snapshot & Variant Fingerprints with deterministic overall and Agent/Seller/Public fingerprints and audience-isolated semantic projections.
- Added tests proving order independence, Passport/evidence sensitivity, upstream mismatch detection, and Agent-only changes leaving Seller/Public fingerprints unchanged.
- Full repository suite: 120 tests passing.
- Advanced current implementation ticket to M2-009 Snapshot Deduplication.

## 0.1.6 — M2-001 / M2-002 Intelligence Bridge foundation
- Accepted M2-001 Governed-State Read Contract with a locked, schema-backed anti-corruption boundary for governed production intelligence.
- Added fail-closed validation for property identity, QA/production/publication states, Passport lineage references, dependency scopes, and SHA-256 fingerprints.
- Accepted M2-002 Snapshot Persistence Completion with canonical `core.properties` anchoring, immutable snapshot children, requirement results, semantic diffs, dependency indexes, and accepted-snapshot semantic immutability.
- Added insert-only snapshot repository adapters and contract/persistence/unit tests.
- Full repository suite: 97 tests passing before final manifest validation.
- Advanced current implementation ticket to M2-003 Snapshot Requirement Registry.

## 0.1.5 — M1-014 / M1-016 completion
- Accepted M1-014 Transition Engine with idempotent command replay, authorization-before-state-access, row-locked state transitions, fail-closed guard evaluation, immutable audit records, correlation/causation events, compare-and-swap conflict handling, and infrastructure-failure escalation for transaction rollback.
- Accepted M1-015 Database Roles & Grants with separate kernel, audit, outbox-worker, operations-reader, and migration roles plus executable PostgreSQL privilege assertions.
- Accepted M1-016 Kernel Certification Suite covering success, rejected guards, unauthorized callers, duplicate commands, state conflicts, audit immutability, outbox recovery contracts, duplicate delivery protection, and rollback escalation.
- Added missing governed reason codes used by guard and transition outcomes through additive migration `0161_kernel_reason_codes.sql`.
- Full repository suite: 84 tests passing.
- Milestone 1 — Governed Lifecycle Kernel is now ACCEPTED. Next build unit: M2-001 Governed-State Read Contract.

## 0.1.4
- Accepted M1-012 Guard Runtime with registry-backed read-only, fail-closed guard evaluation.
- Accepted M1-013 State Adapter Framework with locking and optimistic state-version enforcement.
- Added `operations.kernel_test_entities` migration and expanded unit/persistence coverage.

## 0.1.0
- Created production repository skeleton.
- Added architecture lock, contract manifest, build manifest, and implementation backlog.
- Started M1-001 Repository Bootstrap.

## 0.1.1 - Milestone 1 foundation runtime
- Accepted M1-001 through M1-005.
- Added locked contract files and SHA-256 manifest verification.
- Added fail-closed registry loading and cross-reference validation.
- Added canonical serialization and semantic hashing library.
- Added PostgreSQL foundation migrations and reference-table DDL.
- Added contract, registry, serialization, and persistence tests.

## 0.1.0 — M1-006 / M1-007 implementation
- Added registry-backed reference values and idempotent seed migration.
- Added event type, guard ID, and data-classification reference tables through an additive migration.
- Added immutable audit event, state-transition, and guard-evaluation tables and indexes.
- Added append-only audit mutation protection and insert-only repository adapters.
- Added structural, reconciliation, and repository tests.
## 0.1.2 — M1-008 / M1-009 implementation
- Accepted M1-008 Processed Command Ledger with canonical request-hash idempotency and conflict detection.
- Accepted M1-009 Transactional Outbox with at-least-once delivery, `FOR UPDATE SKIP LOCKED` claims, leases, retries, dead-letter handling, and consumer idempotency ledger.
- Added project-level `pytest.ini` so repository-root imports are deterministic across test runners.
- Expanded the full repository test suite to 40 passing tests.
- Advanced the current implementation ticket to M1-010 Event Runtime.


## 0.1.3 — M1-010 / M1-011
- Implemented Event Runtime with registry-backed type/version lookup, producer authorization, reason-code validation, JSON payload validation, deterministic payload hashing, immutable event persistence, and same-transaction outbox enqueue.
- Added event envelope and generic payload JSON schemas plus registry schema/topic bindings.
- Implemented Transition Registry Runtime with typed definitions, ID/state-signature resolution, ambiguity protection, and fail-closed caller authorization.
- Added unit and contract tests for event validation, persistence ordering, transition resolution, and unauthorized callers.
- Advanced M1-010 and M1-011 to ACCEPTED; M1-012 Guard Runtime is now IN_PROGRESS.

## 0.1.7 — M2-003 through M2-005
- Added machine-readable snapshot requirement registries for core identity, property identity, and optional lot/location capabilities.
- Added deterministic completeness evaluation with COMPLETE, PARTIAL_VALID, BLOCKED, and INVALID outcomes.
- Added fail-closed production finding freezer that preserves governed values/wording and excludes blocked, deprecated, superseded, and internal-only findings from production snapshot findings.
- Added additive snapshot requirement reason-code migration and contract/unit tests.

## 0.1.11 - 2026-09-16

- Accepted M2-015 Dependency Reverse Lookup.
- Accepted M2-016 Single-Change Impact Evaluator.
- Accepted M2-017 Impact Persistence.
- Added indexed reverse lookup across current snapshot dependency consumers with a forward-compatible report-dependency adapter.
- Added deterministic NO_IMPACT / DIRTY / BLOCKED / INVALIDATION_REQUIRED / REVIEW_REQUIRED evaluation.
- Added persisted impact decisions with rule version, reason code, fingerprints, correlation, and idempotent logical uniqueness.
- Added dependency impact audit/event taxonomy without publication mutation.
- Advanced current engineering ticket to M2-018 Bulk Dependency Change Batches.

## 0.1.12 — Milestone 2 completion
- Accepted M2-018 Bulk Dependency Change Batches with deterministic immutable membership, idempotent source-change batches, resumable item states, and reconciled batch counts.
- Accepted M2-019 Bulk Impact Evaluator using deterministic chunking and the governed single-change evaluator/persistence path.
- Accepted M2-020 Block / Invalidation Escalation with invalidation-as-recommendation, non-destructive blocked outcomes, and governed REVIEW_REQUIRED operations items.
- Accepted M2-021 Milestone 2 Certification Suite, including fleet-scale deterministic impact fixtures and publication-boundary tests.
- Full repository suite: 162 tests passing.
- Milestone 2 — Intelligence Bridge is now ACCEPTED. Advanced current implementation ticket to M3-001 Regeneration Job Persistence Completion.

## 0.1.13 — M3-001 through M3-003
- Added regeneration job persistence and active-target uniqueness.
- Added deterministic regeneration priority registry/resolver.
- Added semantic job target key engine.

## 0.1.15 — M3-007 through M3-009
- Accepted M3-007 Variant-Specific Job Freshness with audience-specific semantic fingerprint checks; irrelevant audience changes do not stale work while relevant semantic changes do.
- Accepted M3-008 Report Persistence Completion with immutable semantic report/version records, consumed dependency persistence, semantic uniqueness constraints, report diff persistence reservation, and reverse dependency indexes.
- Accepted M3-009 Report Version Counter with concurrency-safe per-property/per-variant allocation using row locking; MAX(version)+1 is prohibited.
- Full repository suite: 202 tests passing.
- Advanced current implementation ticket to M3-010 Canonical Report Schema.

## 0.1.16 — M3-010 through M3-012
- Accepted M3-010 Canonical Report Schema with a renderer-neutral semantic payload contract, local schema resolution, cross-reference validation, and explicit rejection of presentation-only fields.
- Accepted M3-011 Variant Policy Registry with fail-closed AGENT/SELLER/PUBLIC classification and publication-scope rules.
- Accepted M3-012 Report Section Registry with deterministic ordering, required/optional audience contracts, finding-type mappings, and governed fallback behavior.
- Full repository suite: 214 tests passing.
- Advanced current implementation ticket to M3-013 Finding Selection Engine.
## 0.1.17 — M3-013 through M3-016
- Accepted M3-013 Finding Selection Engine with fail-closed audience scope/classification filtering and deterministic canonical section assignment.
- Accepted M3-014 Approved Wording Resolver; report building now requires exact audience-approved wording and wording versions with no cross-tier fallback or ad hoc paraphrase.
- Accepted M3-015 Friendly Label Resolver with a governed Agent/Seller/Public label registry covering every report-facing finding type.
- Accepted M3-016 Glossary Resolver with contextual terms plus universal verification/freshness terms and audience-specific definitions.
- Added tests for audience isolation, missing wording, label coverage, contextual glossary inclusion, and limitation-preserving definitions.
- Advanced current implementation ticket to M3-017 Report Dependency Manifest Builder.


## 0.1.22 — M4-002 through M4-004
- Accepted M4-002 Render Version Counters with concurrency-safe per-report/per-render-type allocation using row locks; `MAX(version)+1` is prohibited.
- Accepted M4-003 Render Contract Registry with locked WEB, PDF, PRINT, and MOBILE_PREVIEW contracts, required presentation inputs, MIME/channel definitions, and semantic non-invention rules.
- Accepted M4-004 Presentation Input Hash Engine with deterministic dependency ordering and strict separation between semantic report identity and render-specific identity.
- Full repository suite: 288 tests passing; repository validation PASS.
- Advanced current implementation ticket to M4-005 Media Slot Binding.

## 0.1.23 — M4-005 through M4-007
- Accepted M4-005 Media Slot Binding with subject-property isolation, approval/rights checks, safe optional omission, required-slot blocking, and exact MEDIA dependency capture.
- Accepted M4-006 Diagram Slot Binding with property/finding lineage checks, APPROVED/PASS gating, safe omission/blocking, and exact DIAGRAM dependency capture.
- Accepted M4-007 Render Request Service, connecting render contracts, TEMPLATE, BRANDING, governed media, and governed diagrams into one deterministic presentation-input identity without changing semantic report identity.
- Full repository suite: 299 tests passing; repository validation PASS.
- Advanced current implementation ticket to M4-008 WEB Render Adapter.


## 0.1.24 — M4-008 through M4-011
- Accepted M4-008 WEB Render Adapter with deterministic UTF-8 HTML, escaping, canonical structure preservation, and no semantic invention or publication behavior.
- Accepted M4-009 PDF Render Adapter with deterministic ReportLab invariant-mode PDF generation from governed canonical report text only.
- Accepted M4-010 PRINT Render Adapter with deterministic US Letter PDF output as a presentation-only variant over the same governed semantic content.
- Accepted M4-011 Render Deduplication scoped to report ID + render type + presentation input hash; failed/stale/invalidated/archived renders are not reusable.
- Full repository suite: 307 tests passing; repository validation PASS.
- Advanced current implementation ticket to M4-012 Render Validation.

## 0.1.25 — M4-012 through M4-017
- Accepted M4-012 Render Validation with fail-closed render-contract, MIME, artifact hash/size, storage, QA/health, publication-eligibility, and source-report checks.
- Accepted M4-013 Render Artifact Immutability with READY artifact/dependency protection at the PostgreSQL boundary.
- Accepted M4-014 Storage Integrity with independent stored-byte hash/size verification.
- Accepted M4-015 Publication Persistence Completion with explicit semantic-current pointers, per-channel pointers, and append-only publication history.
- Accepted M4-016 Current Semantic Report Model; currentness is pointer-based and never inferred through MAX(version).
- Accepted M4-017 Publication Channel Pointer Model for independent WEB, PDF_DOWNLOAD, and PRINT current artifacts.
- Full repository suite: 323 tests passing; repository validation PASS.
- Advanced current implementation ticket to M4-018 Publication Staging.

## 0.1.27 — M4-022 through M4-032
- Accepted the remaining controlled-publication lifecycle: supersession/history, presentation-only promotion, unpublish, republish, rollback, invalidation, withdrawal, freeze controls, stable delivery routing, and cache invalidation events.
- Rollback requires a historically published target that still passes current eligibility/freshness checks.
- Stable routes resolve explicit current pointers; version numbers are never embedded into the canonical delivery path.
- Publication history remains append-only and current-state changes remain pointer-based.
- Milestone 4 certification suite accepted; full repository suite: 350 tests passing; repository validation PASS.
- Milestone 4 status: ACCEPTED. Advanced current implementation ticket to M5-001 Release Persistence Completion.

## 0.1.29 — M5-002 through M5-004
- Accepted M5-002 Release Policy Registry with machine-readable allowed audience/channel boundaries, deterministic membership ordering, conflict rejection, and mandatory membership freeze.
- Accepted M5-003 Deterministic Membership Resolver with exact scope filtering, stable ordinal assignment, population-only membership fingerprints, and fail-closed conflicting duplicate detection.
- Accepted M5-004 Release Manifest Freezer with exact target snapshot/report/render lineage, semantic/presentation fingerprints, deterministic manifest hashing, idempotent freeze behavior, and PostgreSQL immutability guards after freeze.
- Full repository suite: 367 tests passing; repository validation PASS.
- Advanced current implementation ticket to M5-005 Release Item Lifecycle.
## 0.1.32 — M5-023 through M5-026
- Accepted M5-023 Incident Persistence & Lifecycle with durable incident identity, severity/state, append-only lifecycle history, and concurrency-safe state transitions.
- Accepted M5-024 Automatic Containment with registry-governed containment selection; unsafe publication targets can be frozen and release/regeneration targets held without selecting a recovery action.
- Accepted M5-025 Recovery Command Framework with explicit operator requests, command-type registry validation, canonical request hashing, idempotency keys, durable command state, and append-only command history.
- Accepted M5-026 Explicit Recovery Actions for releasing publication freezes, requeueing recoverable regeneration jobs, retrying blocked/failed release items, revalidating publication targets, and resolving incidents.
- Added governed incident/recovery reason codes through additive reference migration 0167.
- Full repository suite: 401 tests passing; repository validation PASS.
- Advanced current implementation ticket to M5-027 Backup Verification.

## 0.1.34 — M6-001 through M6-003
- Accepted M6-001 Service Identity Registry with stable service IDs, trust tiers, dedicated database roles, allowed authentication methods, and explicit capability sets.
- Accepted M6-002 Service Authentication Boundary with short-lived HMAC-SHA256 service assertions, externally supplied key material, audience/lifetime/nonce validation, constant-time signature verification, and post-authentication capability enforcement.
- Accepted M6-003 Database Least-Privilege Completion with dedicated runtime NOLOGIN roles, PUBLIC/default-privilege revocation, service-specific grants, publication-pointer authority isolation, and current-PUBLIC-only database projections for edge delivery.
- Full repository suite: 421 tests passing; repository validation PASS.
- Advanced current implementation ticket to M6-004 Human Role Registry.

## 0.1.35 — M6-004 through M6-006
- Accepted M6-004 Human Role Registry with the exact locked human-role set, explicit data-classification permissions, action permissions, and property-scope modes; AGENT is explicitly non-admin and PUBLIC is sanitized-current-publication only.
- Accepted M6-005 Authorization Policy Engine with fail-closed role/action/classification evaluation and explicit denial reasons; unknown roles/actions do not inherit authority.
- Accepted M6-006 Property-Scoped Authorization: SELLER and AGENT require explicit property assignment, OPERATIONS and ADMIN are fleet-scoped, and protected property actions require a property identifier.
- Full repository suite: 429 tests passing; repository validation PASS.
- Advanced current implementation ticket to M6-007 Audience Enforcement.

## 0.1.37 — M6-010 through M6-012
- Accepted M6-010 Private Media Authorization with visibility-to-classification mapping, property-scoped authorization, and APPROVED/CLEARED media requirements.
- Accepted M6-011 Historical Report Access Control: current-report access does not imply history; historical access requires the dedicated action, audience eligibility, classification permission, and property scope.
- Accepted M6-012 Privileged Command Authorization with a locked command-policy registry mapping command types to required actions, classifications, and property-scope requirements; unknown commands fail closed.
- Full repository suite: 448 tests passing; repository validation PASS.
- Advanced current implementation ticket to M6-013 Break-Glass Controls.
## 0.1.40 — M7-002 through M7-004

- Accepted Certification Candidate Freeze with deterministic frozen candidate evidence bound to the M7 production run.
- Accepted Contract / Build Manifest Pinning, including verification of every locked contract SHA-256 before pinning.
- Accepted Environment Parity Verification with locked required/exact-match runtime attributes and immutable evidence persistence.
- Full repository validation: 493 tests passed; repository bootstrap validation PASS.


## 0.1.41 — M7-005 through M7-007
- Added locked production configuration validation with fail-closed required/prohibited-value checks and immutable validation evidence.
- Added deterministic real-property pilot eligibility resolution using governed identity, snapshot QA/completeness, incident, freeze, and pilot-cap rules.
- Added immutable pilot membership evidence with separate reproducible membership fingerprint.
- Added shadow-mode orchestration over eligible real properties with a deliberately non-publication-capable executor interface and deterministic evidence hashing.
- Added M7-005–M7-007 unit/persistence coverage; full suite: 503 passed.

## 0.1.42 — M7-008 through M7-010
- Added immutable production shadow-cycle and target-result tracking with deterministic evidence fingerprints.
- Added locked manual-audit sampling policy with failed-shadow-first, deterministic hash-ranked selection over the frozen pilot population.
- Added append-only manual-audit evidence capture with checklist/version/reviewer lineage and canonical evidence hashes.
- Preserved the certification boundary: these tickets record observation and audit evidence only; shadow acceptance and go-live verdict logic remain downstream.

## 0.1.43 — M7-011 through M7-013
- Accepted Shadow Acceptance Engine with three-consecutive-cycle, frozen-membership, latest-cycle manual-audit, complete-sample, PASS-only acceptance rules and deterministic evidence hashing.
- Accepted Go-Live Stop Condition Engine with fail-closed evaluation of environment/configuration/shadow status, hard-zero metrics, critical incidents, global freezes, candidate revocation, and candidate fingerprint drift.
- Accepted Limited Approval as a distinct, non-FULL approval bound to candidate/pilot/shadow/stop evidence, capped at 25 properties and 24 hours.
- Added immutable persistence for shadow acceptance, stop-condition results, and Limited Approval.
- Full repository suite: 520 tests passing; repository validation PASS.
- Advanced current implementation ticket to M7-014 Cohort Registry & Membership Freezing.

## 0.1.44 — M7-014 through M7-016
- Accepted Cohort Registry & Membership Freezing with exact 25-property deterministic membership bound to the candidate, frozen pilot membership, Limited Approval, and allowed variants.
- Accepted Cohort 25 Deployment with active-approval and current-stop-condition gates, frozen-member-only activation, per-property evidence, and fail-fast behavior that prevents later members from activating after the first failure.
- Accepted Cohort Evidence Certification with exact count, all-PASS, and membership/candidate/approval fingerprint requirements; incomplete or drifted rollout evidence fails closed.
- Added immutable PostgreSQL persistence for cohort membership, member ordinals, deployment/item evidence, and cohort certification evidence.
- Full repository suite: 527 tests passing; repository validation PASS.
- Advanced current implementation ticket to M7-017 Cohort 100 Deployment.

## 0.1.47 — M7-023 through M7-026
- Accepted Cohort Rollback / Containment using the immutable rollback baseline, reverse deterministic restoration, and automatic containment evidence on restore failure.
- Accepted Certification Evidence Bundle with fail-closed required-evidence completeness/PASS checks and deterministic immutable bundle fingerprints.
- Accepted Certification Revocation as separate append-only candidate-bound evidence rather than mutation of historical approval records.
- Accepted Formal FULL_APPROVAL under a locked policy requiring a PASS evidence bundle, CLEAR stop conditions, no active matching revocation, and PASS certification for COHORT_25, COHORT_100, COHORT_500, and REMAINING_FLEET.
- Added immutable PostgreSQL persistence for rollback runs/items, final evidence bundles/items, certification revocations, and FULL_APPROVAL records.
- Full repository suite: 547 tests passing; repository validation PASS.
- Advanced current implementation ticket to M7-027 Milestone 7 Final Certification Suite.

## 0.1.48 — M7-027 final certification gate implemented; live PostgreSQL gate BLOCKED
- Added locked M7 final-certification policy covering rollout, hard-zero, FULL_APPROVAL, stop-condition, and live PostgreSQL requirements.
- Added deterministic Milestone 7 final certification evaluator with PASS / FAIL / BLOCKED outcomes.
- Added explicit live PostgreSQL certification requirements for migrations, immutability triggers, least-privilege grants, locking/concurrency, and backup/restore behavior.
- Added certification tests proving GO only when every production gate passes and BLOCKED when live PostgreSQL checks have not executed.
- M7-027 remains BLOCKED in this runtime because PostgreSQL server/client binaries and a PostgreSQL Python driver are unavailable; M7 is not falsely marked production-certified.


## 0.1.53 — GitHub first-push bootstrap for blocked M7-027
- Added a repository `.gitignore` that excludes Python/test noise and generated certification evidence from candidate source identity.
- Added `bootstrap_github_remote.py` to attach the exact committed candidate to an existing GitHub repository without rewriting the source commit or force-pushing.
- Prepared the package to carry a real first Git commit so the M7 candidate can be bound to an actual source revision/tree before live PostgreSQL certification runs.
- M7-027 remains BLOCKED until candidate-bound live PostgreSQL evidence passes all five required checks.
