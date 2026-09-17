BEGIN;
CREATE OR REPLACE FUNCTION snapshot.protect_accepted_snapshot_semantics()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.qa_status = 'PASS' AND (
      NEW.property_id IS DISTINCT FROM OLD.property_id OR
      NEW.snapshot_sequence IS DISTINCT FROM OLD.snapshot_sequence OR
      NEW.snapshot_reason IS DISTINCT FROM OLD.snapshot_reason OR
      NEW.governed_state_version IS DISTINCT FROM OLD.governed_state_version OR
      NEW.source_read_token IS DISTINCT FROM OLD.source_read_token OR
      NEW.intelligence_schema_version IS DISTINCT FROM OLD.intelligence_schema_version OR
      NEW.governance_schema_version IS DISTINCT FROM OLD.governance_schema_version OR
      NEW.model_version IS DISTINCT FROM OLD.model_version OR
      NEW.semantic_fingerprint IS DISTINCT FROM OLD.semantic_fingerprint OR
      NEW.agent_semantic_fingerprint IS DISTINCT FROM OLD.agent_semantic_fingerprint OR
      NEW.seller_semantic_fingerprint IS DISTINCT FROM OLD.seller_semantic_fingerprint OR
      NEW.public_semantic_fingerprint IS DISTINCT FROM OLD.public_semantic_fingerprint OR
      NEW.snapshot_hash IS DISTINCT FROM OLD.snapshot_hash OR
      NEW.snapshot_completeness_status IS DISTINCT FROM OLD.snapshot_completeness_status OR
      NEW.supersedes_snapshot_id IS DISTINCT FROM OLD.supersedes_snapshot_id OR
      NEW.created_by IS DISTINCT FROM OLD.created_by
  ) THEN
    RAISE EXCEPTION 'accepted snapshot semantic fields are immutable';
  END IF;
  RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS trg_snapshot_parent_semantic_immutable ON snapshot.intelligence_snapshots;
CREATE TRIGGER trg_snapshot_parent_semantic_immutable
BEFORE UPDATE ON snapshot.intelligence_snapshots
FOR EACH ROW EXECUTE FUNCTION snapshot.protect_accepted_snapshot_semantics();
COMMIT;
