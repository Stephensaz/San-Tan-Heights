-- STH M7-027 remediation: create shared immutable-row trigger support before certification tables consume it.
BEGIN;
CREATE SCHEMA IF NOT EXISTS shared;

CREATE OR REPLACE FUNCTION shared.raise_immutable_row()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'immutable row cannot be updated or deleted'
      USING ERRCODE = '55000';
END;
$$;
COMMIT;
