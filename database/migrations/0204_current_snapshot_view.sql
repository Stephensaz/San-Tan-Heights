BEGIN;
CREATE OR REPLACE VIEW snapshot.current_snapshot_view AS
SELECT DISTINCT ON (s.property_id)
    s.property_id,
    s.snapshot_id AS current_snapshot_id,
    s.snapshot_sequence,
    s.semantic_fingerprint,
    s.agent_semantic_fingerprint,
    s.seller_semantic_fingerprint,
    s.public_semantic_fingerprint,
    s.snapshot_completeness_status,
    s.qa_status,
    s.created_at
FROM snapshot.intelligence_snapshots s
WHERE s.qa_status = 'PASS'
  AND s.snapshot_completeness_status IN ('COMPLETE','PARTIAL_VALID')
ORDER BY s.property_id, s.snapshot_sequence DESC;
COMMIT;
