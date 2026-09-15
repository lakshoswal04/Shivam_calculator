-- 012 - Company profile fields, per-org CIN, and writable issue history
--
-- Three changes, all needed before a user can enter their own company rather
-- than pick one of the seeded ones.
--
-- 1. Listed issuers are searched by ticker and ISIN, which the schema had no
--    place for. They go on company_classifications, not companies: both are
--    only meaningful while listed, and that table is already effective-dated
--    with an exclusion constraint, so a delisting retires them instead of
--    leaving a stale ticker on the company for ever.
--
-- 2. companies.cin was UNIQUE across the whole platform while the duplicate
--    pre-check in create_company runs under RLS and cannot see other tenants.
--    A CIN held by another organisation therefore passed the check, violated
--    the index, and surfaced as a 500. Two advisory firms may legitimately
--    both hold the same client on file, so uniqueness belongs per org.
--
-- 3. company.issues has existed since 005 and nothing has ever written to it.
--    Recording issue history from a browser form needs an idempotency key, or
--    a retry after an ambiguous network failure double-inserts.

BEGIN;

ALTER TABLE company.companies
  ADD COLUMN registered_office text;
COMMENT ON COLUMN company.companies.registered_office IS
  'Free-text registered office. Self-declared; no registry verification is claimed.';

ALTER TABLE company.company_classifications
  ADD COLUMN ticker_symbol text,
  ADD COLUMN isin          text;

ALTER TABLE company.company_classifications
  ADD CONSTRAINT ticker_symbol_shape
    CHECK (ticker_symbol IS NULL OR ticker_symbol ~ '^[A-Za-z0-9&.-]{1,20}$'),
  ADD CONSTRAINT isin_shape
    CHECK (isin IS NULL OR isin ~ '^IN[A-Za-z0-9]{9}[0-9]$'),
  -- An unlisted company has neither. Allowing them would let a delisted
  -- classification keep identifiers that no longer address anything.
  ADD CONSTRAINT listed_identifiers_need_listing
    CHECK (listed_status = 'LISTED' OR (ticker_symbol IS NULL AND isin IS NULL));

-- Per-org, not global. See note 2 above.
ALTER TABLE company.companies DROP CONSTRAINT companies_cin_key;
CREATE UNIQUE INDEX companies_org_cin_key
  ON company.companies (org_id, cin) WHERE cin IS NOT NULL;

-- Search: ILIKE under an RLS predicate, no pg_trgm. The extension is not
-- installed by 001 and enabling one is a privilege question on managed
-- Postgres; a sequential scan behind tenant isolation is fine into the
-- thousands of rows. Revisit if a single org passes ~5k companies.
CREATE INDEX companies_name_lower_idx ON company.companies (lower(name));
CREATE INDEX classifications_ticker_lower_idx
  ON company.company_classifications (lower(ticker_symbol)) WHERE ticker_symbol IS NOT NULL;
CREATE INDEX classifications_isin_lower_idx
  ON company.company_classifications (lower(isin)) WHERE isin IS NOT NULL;

ALTER TABLE company.issues
  ADD COLUMN client_ref uuid;
COMMENT ON COLUMN company.issues.client_ref IS
  'Idempotency key minted by the client per row, so a retried submission cannot double-insert.';

CREATE UNIQUE INDEX issues_client_ref_key
  ON company.issues (company_id, client_ref) WHERE client_ref IS NOT NULL;

-- status was free text with no vocabulary. The values are already assumed by
-- the reporting code; pinning them stops a typo becoming a silent category.
ALTER TABLE company.issues
  ADD CONSTRAINT issue_status_vocab
    CHECK (status IN ('PLANNED', 'ANNOUNCED', 'OPEN', 'CLOSED', 'ALLOTTED', 'WITHDRAWN'));

COMMIT;

-- rollback:
--   ALTER TABLE company.issues DROP CONSTRAINT issue_status_vocab;
--   DROP INDEX IF EXISTS company.issues_client_ref_key;
--   ALTER TABLE company.issues DROP COLUMN client_ref;
--   DROP INDEX IF EXISTS company.classifications_isin_lower_idx;
--   DROP INDEX IF EXISTS company.classifications_ticker_lower_idx;
--   DROP INDEX IF EXISTS company.companies_name_lower_idx;
--   DROP INDEX IF EXISTS company.companies_org_cin_key;
--   ALTER TABLE company.companies ADD CONSTRAINT companies_cin_key UNIQUE (cin);
--   ALTER TABLE company.company_classifications
--     DROP CONSTRAINT listed_identifiers_need_listing,
--     DROP CONSTRAINT isin_shape, DROP CONSTRAINT ticker_symbol_shape,
--     DROP COLUMN isin, DROP COLUMN ticker_symbol;
--   ALTER TABLE company.companies DROP COLUMN registered_office;

-- ---------------------------------------------------------------------------
-- Aggregate condition operators.
--
-- legal.validate_condition_ast is one half of a dual implementation; the other
-- is validate() in pipeline/lib/conditions.py, and a pipeline test asserts the
-- two never disagree. Both gain count_where and any_where together.
--
-- Until now the evaluator could only walk dicts, so a rule could not address a
-- list of records at all. Previous-issue history is a list, so no rule could be
-- authored against it without changing engine code -- which FR-INP-006 says
-- must not be necessary. These two operators reduce a list to a scalar first:
--
--   {"op": "count_where", "field": "company.previous_issues",
--    "where": {"op": "eq", "field": "issue_type", "value": "PRIVATE_PLACEMENT"},
--    "op2": "lte", "value": 2}
--
--   {"op": "any_where", "field": "company.previous_issues",
--    "where": {"op": "eq", "field": "issue_type", "value": "BONUS"}}

BEGIN;

CREATE OR REPLACE FUNCTION legal.validate_condition_ast(node jsonb)
RETURNS boolean LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE op text; arg jsonb;
BEGIN
    IF jsonb_typeof(node) <> 'object' OR NOT node ? 'op' THEN RETURN false; END IF;
    op := node ->> 'op';
    IF op IN ('AND','OR') THEN
        IF NOT node ? 'args' OR jsonb_typeof(node -> 'args') <> 'array'
           OR jsonb_array_length(node -> 'args') < 1 THEN RETURN false; END IF;
        FOR arg IN SELECT * FROM jsonb_array_elements(node -> 'args') LOOP
            IF NOT legal.validate_condition_ast(arg) THEN RETURN false; END IF;
        END LOOP;
        RETURN true;
    ELSIF op = 'NOT' THEN
        RETURN node ? 'arg' AND legal.validate_condition_ast(node -> 'arg');
    ELSIF op IN ('exists','not_exists') THEN
        RETURN node ? 'field';
    ELSIF op IN ('eq','ne','gt','gte','lt','lte','in','not_in') THEN
        IF NOT (node ? 'field' AND node ? 'value') THEN RETURN false; END IF;
        IF op IN ('in','not_in') AND jsonb_typeof(node -> 'value') <> 'array' THEN
            RETURN false;
        END IF;
        RETURN true;
    ELSIF op IN ('count_where','any_where') THEN
        IF NOT (node ? 'field' AND node ? 'where') THEN RETURN false; END IF;
        IF NOT legal.validate_condition_ast(node -> 'where') THEN RETURN false; END IF;
        IF op = 'any_where' THEN RETURN true; END IF;
        RETURN node ? 'value'
           AND node ->> 'op2' IN ('eq','ne','gt','gte','lt','lte','in','not_in');
    END IF;
    RETURN false;
END $$;

COMMIT;
