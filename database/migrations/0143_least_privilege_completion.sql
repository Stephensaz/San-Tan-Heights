-- M6-003: complete service-specific least privilege.
BEGIN;

-- PUBLIC receives no implicit access to application schemas or objects.
REVOKE ALL ON SCHEMA core, snapshot, reporting, publication, orchestration, audit, operations, security, reference FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA core, snapshot, reporting, publication, orchestration, audit, operations, security, reference FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA core, snapshot, reporting, publication, orchestration, audit, operations, security, reference FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA core, snapshot, reporting, publication, orchestration, audit, operations, security, reference FROM PUBLIC;

-- Public delivery gets only current PUBLIC projections, never base reporting tables.
CREATE OR REPLACE VIEW publication.current_public_reports AS
SELECT c.property_id, c.report_id, r.version_number AS report_version, r.canonical_payload,
       r.canonical_payload_hash, r.report_input_hash, r.qa_status, r.publication_eligible
FROM publication.report_current c
JOIN reporting.report_versions r ON r.report_id=c.report_id
WHERE c.report_variant='PUBLIC' AND r.report_variant='PUBLIC';

CREATE OR REPLACE VIEW publication.current_public_renders AS
SELECT p.property_id, p.channel, p.render_id, rv.report_id, rv.render_type,
       rv.storage_uri, rv.artifact_hash, rv.mime_type, rv.qa_status
FROM publication.channel_pointers p
JOIN reporting.render_versions rv ON rv.render_id=p.render_id
JOIN reporting.report_versions r ON r.report_id=rv.report_id
WHERE p.report_variant='PUBLIC' AND r.report_variant='PUBLIC';

-- Common reference/audit write access for production services.
GRANT USAGE ON SCHEMA reference, audit TO sth_snapshot_service, sth_report_builder, sth_renderer, sth_publication_service, sth_regeneration_worker, sth_release_service, sth_operations_service;
GRANT SELECT ON ALL TABLES IN SCHEMA reference TO sth_snapshot_service, sth_report_builder, sth_renderer, sth_publication_service, sth_regeneration_worker, sth_release_service, sth_operations_service;
GRANT INSERT ON audit.orchestration_events, audit.state_transitions, audit.guard_evaluations, audit.event_outbox TO sth_snapshot_service, sth_report_builder, sth_renderer, sth_publication_service, sth_regeneration_worker, sth_release_service, sth_operations_service;
GRANT SELECT, INSERT ON audit.processed_commands TO sth_snapshot_service, sth_report_builder, sth_renderer, sth_publication_service, sth_regeneration_worker, sth_release_service, sth_operations_service;

-- Snapshot service.
GRANT USAGE ON SCHEMA core, snapshot TO sth_snapshot_service;
GRANT SELECT ON core.properties TO sth_snapshot_service;
GRANT SELECT, INSERT, UPDATE ON snapshot.intelligence_snapshots, snapshot.snapshot_findings, snapshot.snapshot_dependencies, snapshot.snapshot_requirement_results, snapshot.snapshot_diffs, snapshot.snapshot_sequence_counters TO sth_snapshot_service;

-- Report builder.
GRANT USAGE ON SCHEMA core, snapshot, reporting TO sth_report_builder;
GRANT SELECT ON core.properties, snapshot.intelligence_snapshots, snapshot.snapshot_findings, snapshot.snapshot_dependencies TO sth_report_builder;
GRANT SELECT, INSERT, UPDATE ON reporting.report_versions, reporting.report_dependencies, reporting.report_version_counters, reporting.report_diffs TO sth_report_builder;

-- Renderer.
GRANT USAGE ON SCHEMA reporting TO sth_renderer;
GRANT SELECT ON reporting.report_versions, reporting.report_dependencies TO sth_renderer;
GRANT SELECT, INSERT, UPDATE ON reporting.render_versions, reporting.render_dependencies, reporting.render_version_counters TO sth_renderer;

-- Publication service: owns current pointers/lifecycle, reads immutable report/render evidence.
GRANT USAGE ON SCHEMA reporting, publication, operations TO sth_publication_service;
GRANT SELECT ON reporting.report_versions, reporting.report_dependencies, reporting.render_versions, reporting.render_dependencies TO sth_publication_service;
GRANT SELECT, INSERT, UPDATE, DELETE ON publication.report_current, publication.channel_pointers TO sth_publication_service;
GRANT SELECT, INSERT, UPDATE ON publication.publication_staging, publication.publication_freezes TO sth_publication_service;
GRANT SELECT, INSERT ON publication.publication_history TO sth_publication_service;
GRANT SELECT ON operations.global_publication_freezes TO sth_publication_service;

-- Regeneration worker: job lifecycle plus delegated report production inputs/outputs.
GRANT USAGE ON SCHEMA core, snapshot, reporting, orchestration TO sth_regeneration_worker;
GRANT SELECT ON core.properties, snapshot.intelligence_snapshots, snapshot.snapshot_findings, snapshot.snapshot_dependencies TO sth_regeneration_worker;
GRANT SELECT, INSERT, UPDATE ON orchestration.regeneration_jobs TO sth_regeneration_worker;
GRANT SELECT, INSERT, UPDATE ON reporting.report_versions, reporting.report_dependencies, reporting.report_version_counters, reporting.report_diffs TO sth_regeneration_worker;

-- Release service: release state and read-only publication/report evidence. Pointer mutation stays with publication service.
GRANT USAGE ON SCHEMA operations, publication, reporting TO sth_release_service;
GRANT SELECT, INSERT, UPDATE ON operations.releases, operations.release_manifests, operations.release_items, operations.release_item_history, operations.release_validation_results, operations.release_approvals TO sth_release_service;
GRANT SELECT ON publication.report_current, publication.channel_pointers, publication.publication_history, reporting.report_versions, reporting.render_versions TO sth_release_service;

-- Operations service: incident/recovery/verification control, but no direct semantic report mutation.
GRANT USAGE ON SCHEMA operations, publication, orchestration, audit TO sth_operations_service;
GRANT SELECT, INSERT, UPDATE ON operations.integrity_sweep_runs, operations.integrity_findings, operations.incidents, operations.incident_history, operations.containment_actions, operations.recovery_commands, operations.recovery_command_history, operations.backup_verifications, operations.restore_verifications, operations.global_publication_freezes, operations.review_items TO sth_operations_service;
GRANT SELECT ON operations.releases, operations.release_manifests, operations.release_items, operations.release_item_history, operations.release_validation_results, operations.release_approvals TO sth_operations_service;
GRANT SELECT ON publication.report_current, publication.channel_pointers, publication.publication_history, publication.publication_staging TO sth_operations_service;
GRANT SELECT, INSERT, UPDATE ON publication.publication_freezes TO sth_operations_service;
GRANT SELECT, UPDATE ON orchestration.regeneration_jobs TO sth_operations_service;
GRANT SELECT ON audit.orchestration_events, audit.state_transitions, audit.guard_evaluations TO sth_operations_service;

-- Read-only current PUBLIC delivery projections only.
GRANT USAGE ON SCHEMA publication TO sth_public_delivery;
GRANT SELECT ON publication.current_public_reports, publication.current_public_renders TO sth_public_delivery;

-- Future objects created by the migration owner are private by default.
ALTER DEFAULT PRIVILEGES FOR ROLE sth_migration IN SCHEMA core, snapshot, reporting, publication, orchestration, audit, operations, security, reference REVOKE ALL ON TABLES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE sth_migration IN SCHEMA core, snapshot, reporting, publication, orchestration, audit, operations, security, reference REVOKE ALL ON SEQUENCES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE sth_migration IN SCHEMA core, snapshot, reporting, publication, orchestration, audit, operations, security, reference REVOKE ALL ON FUNCTIONS FROM PUBLIC;

COMMIT;
