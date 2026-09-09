-- 010 - Store the assessment payload in a typed column
--
-- The full assessment result was being written into `notes`, a text column,
-- so it read back as a string rather than an object. `notes` is for a human
-- note; the result is structured data and belongs in jsonb, where it can also
-- be queried.

BEGIN;

ALTER TABLE assess.assessment_results ADD COLUMN payload jsonb;

COMMENT ON COLUMN assess.assessment_results.payload IS
  'The complete assessment result as returned by the API. Immutable evidence.';
COMMENT ON COLUMN assess.assessment_results.notes IS
  'Free-text note by a person. Never the result payload.';

-- Migrate anything already written into notes as JSON, and clear it.
UPDATE assess.assessment_results
SET payload = notes::jsonb, notes = NULL
WHERE notes IS NOT NULL AND left(btrim(notes), 1) = '{';

CREATE INDEX ON assess.assessment_results USING gin (payload jsonb_path_ops);

COMMIT;

-- rollback:
--   DROP INDEX IF EXISTS assess.assessment_results_payload_idx;
--   ALTER TABLE assess.assessment_results DROP COLUMN IF EXISTS payload;
