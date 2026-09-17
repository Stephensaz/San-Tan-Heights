-- STH M1-007: Immutable-record protection function.
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
