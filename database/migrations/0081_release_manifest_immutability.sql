-- STH M5-004: frozen release membership/manifest immutability.
BEGIN;

CREATE OR REPLACE FUNCTION operations.reject_frozen_release_manifest_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'frozen release manifest is immutable';
END $$;

DROP TRIGGER IF EXISTS trg_release_manifest_immutable ON operations.release_manifests;
CREATE TRIGGER trg_release_manifest_immutable
BEFORE UPDATE OR DELETE ON operations.release_manifests
FOR EACH ROW EXECUTE FUNCTION operations.reject_frozen_release_manifest_mutation();

CREATE OR REPLACE FUNCTION operations.guard_frozen_release_item_membership()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE rid uuid;
BEGIN
  rid := COALESCE(NEW.release_id, OLD.release_id);
  IF EXISTS (SELECT 1 FROM operations.release_manifests m WHERE m.release_id = rid) THEN
    IF TG_OP IN ('INSERT','DELETE') THEN
      RAISE EXCEPTION 'frozen release membership is immutable';
    END IF;
    IF (NEW.release_id,NEW.property_id,NEW.report_variant,NEW.channel,NEW.membership_ordinal,
        NEW.target_snapshot_id,NEW.target_report_id,NEW.target_render_id,
        NEW.target_semantic_fingerprint,NEW.target_presentation_fingerprint)
       IS DISTINCT FROM
       (OLD.release_id,OLD.property_id,OLD.report_variant,OLD.channel,OLD.membership_ordinal,
        OLD.target_snapshot_id,OLD.target_report_id,OLD.target_render_id,
        OLD.target_semantic_fingerprint,OLD.target_presentation_fingerprint) THEN
      RAISE EXCEPTION 'frozen release target evidence is immutable';
    END IF;
  END IF;
  RETURN COALESCE(NEW,OLD);
END $$;

DROP TRIGGER IF EXISTS trg_release_item_frozen_membership ON operations.release_items;
CREATE TRIGGER trg_release_item_frozen_membership
BEFORE INSERT OR UPDATE OR DELETE ON operations.release_items
FOR EACH ROW EXECUTE FUNCTION operations.guard_frozen_release_item_membership();

CREATE OR REPLACE FUNCTION operations.guard_frozen_release_parent_metadata()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM operations.release_manifests m WHERE m.release_id = OLD.release_id) AND
     (NEW.policy_version,NEW.membership_fingerprint,NEW.manifest_fingerprint,NEW.total_item_count)
       IS DISTINCT FROM
     (OLD.policy_version,OLD.membership_fingerprint,OLD.manifest_fingerprint,OLD.total_item_count) THEN
    RAISE EXCEPTION 'frozen release manifest metadata is immutable';
  END IF;
  RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_release_parent_frozen_metadata ON operations.releases;
CREATE TRIGGER trg_release_parent_frozen_metadata
BEFORE UPDATE ON operations.releases
FOR EACH ROW EXECUTE FUNCTION operations.guard_frozen_release_parent_metadata();

COMMIT;
