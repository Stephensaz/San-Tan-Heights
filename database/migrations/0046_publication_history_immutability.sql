-- STH M4-015: publication history is append-only evidence.
BEGIN;
DROP TRIGGER IF EXISTS trg_publication_history_immutable ON publication.publication_history;
CREATE TRIGGER trg_publication_history_immutable
BEFORE UPDATE OR DELETE ON publication.publication_history
FOR EACH ROW EXECUTE FUNCTION audit.prevent_immutable_mutation();
COMMIT;
