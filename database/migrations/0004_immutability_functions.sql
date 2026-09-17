-- STH M7-027 remediation: make the generic immutable-record trigger function
-- available before any table-specific immutability trigger migrations execute.
BEGIN;
CREATE OR REPLACE FUNCTION audit.prevent_immutable_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'immutable audit records cannot be updated or deleted'
      USING ERRCODE = '55000';
END;
$$;
COMMIT;
