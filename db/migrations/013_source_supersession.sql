-- 013 - Supersession: which edition of a reissued circular is the law in force
--
-- SEBI republishes a master circular under an unchanged name every year or two.
-- The master-circular listing carries 11 editions of "Master Circular for
-- Depositories" and 10 of "Master Circular for Mutual Funds", of which exactly
-- one is current. Until now the corpus had no way to say which: every edition
-- would land in the Legal Library as an equally citable source, and a provision
-- search would return wording withdrawn in 2012 beside the text in force.
--
-- The columns are deliberately narrow. legal_sources already carries
-- publication_date, status and version, so this adds only what is genuinely
-- missing: which family an edition belongs to, which edition replaced it, and
-- - the important one - on whose authority that claim is made.
--
-- supersession_basis is what keeps this honest. The pipeline infers
-- supersession from a title and a date (pipeline/lib/supersession.py), which is
-- NOT the reviewer's declaration that consolidation_status asks for. Recording
-- the basis means a later reviewer can tell the two apart, and can promote an
-- inferred call to DECLARED without the schema having to guess.

BEGIN;

ALTER TABLE legal.legal_sources
    ADD COLUMN document_family    text,
    ADD COLUMN superseded_by      uuid REFERENCES legal.legal_sources(source_id),
    ADD COLUMN supersession_basis text;

COMMENT ON COLUMN legal.legal_sources.document_family IS
  'Normalised title shared by every edition of one reissued circular.';
COMMENT ON COLUMN legal.legal_sources.superseded_by IS
  'The edition that replaced this one; NULL while this is the edition in force.';
COMMENT ON COLUMN legal.legal_sources.supersession_basis IS
  'How supersession was established. INFERRED_TITLE_DATE is a pipeline heuristic, '
  'not a reviewer''s confirmation, and must not be read as one.';

ALTER TABLE legal.legal_sources
    ADD CONSTRAINT supersession_basis_known
        CHECK (supersession_basis IS NULL
               OR supersession_basis IN ('DECLARED','INFERRED_TITLE_DATE')),
    -- status was an unconstrained text column defaulting to 'ACTIVE'.
    ADD CONSTRAINT status_known
        CHECK (status IN ('ACTIVE','SUPERSEDED','WITHDRAWN')),
    -- A document cannot be called superseded without saying on whose authority.
    ADD CONSTRAINT superseded_needs_basis
        CHECK (status <> 'SUPERSEDED' OR supersession_basis IS NOT NULL),
    ADD CONSTRAINT not_superseded_by_itself
        CHECK (superseded_by IS NULL OR superseded_by <> source_id);

-- A superseded edition must also name what replaced it, or "superseded" is just
-- a way of hiding a document with nothing to point the reader at instead.
--
-- This cannot be a CHECK. superseded_by references another row of this same
-- table whose source_id is generated on insert, so the loader inserts every
-- source first and wires the successors in a second pass - the same two-pass
-- shape legal_provisions.parent_id already uses. A CHECK is immediate and would
-- reject the first superseded row before its successor exists. Postgres can
-- defer only FK, UNIQUE and EXCLUDE constraints, so the rule is expressed as a
-- deferred constraint trigger: still enforced, but at COMMIT, which is the
-- point at which the claim is actually meant to hold.
-- The row is re-read by source_id rather than trusting NEW. A deferred trigger
-- fires at COMMIT carrying the row image from the statement that queued it, so
-- the INSERT's event still shows superseded_by NULL even after the second pass
-- has filled it in. Only the committed state is worth asserting against.
CREATE FUNCTION legal.assert_supersession_complete() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    cur legal.legal_sources%ROWTYPE;
BEGIN
    SELECT * INTO cur FROM legal.legal_sources WHERE source_id = NEW.source_id;
    IF NOT FOUND THEN           -- deleted later in the same transaction
        RETURN NULL;
    END IF;
    IF cur.status = 'SUPERSEDED' AND cur.superseded_by IS NULL THEN
        RAISE EXCEPTION
            'legal_sources.document_key=% is SUPERSEDED but names no successor',
            cur.document_key;
    END IF;
    RETURN NULL;
END $$;

CREATE CONSTRAINT TRIGGER superseded_needs_successor
    AFTER INSERT OR UPDATE ON legal.legal_sources
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION legal.assert_supersession_complete();

CREATE INDEX ON legal.legal_sources (document_family, publication_date DESC);
CREATE INDEX ON legal.legal_sources (status);

-- The production rule view must never resolve to withdrawn text. This is the
-- reason the feature exists, so it is enforced as a quality check rather than
-- left to reviewer discipline: db/tests and ./dev.sh test both fail the build
-- when any check returns a non-zero count.
-- Rebuilt from 011, NOT from 006: 011 renamed rule_without_provision to
-- rule_without_provision_anchor and deliberately dropped
-- ambiguous_citation_used_by_rule as a gate, keeping it advisory in
-- legal.v_citation_advisories. Re-adding either here would silently undo that.
CREATE OR REPLACE VIEW legal.v_quality_checks AS
SELECT * FROM (
  VALUES
    ('rule_without_source',
     (SELECT count(*) FROM legal.legal_rule_versions WHERE source_id IS NULL)),
    ('rule_without_provision_anchor',
     (SELECT count(*) FROM legal.legal_rule_versions WHERE provision_id IS NULL)),
    ('rule_without_effective_from',
     (SELECT count(*) FROM legal.legal_rule_versions WHERE effective_from IS NULL)),
    ('approved_rule_still_flagged',
     (SELECT count(*) FROM legal.legal_rule_versions
       WHERE legal_review_status = 'APPROVED' AND human_review_required)),
    ('pending_rule_in_production_view',
     (SELECT count(*) FROM legal.v_active_rule_versions WHERE legal_review_status <> 'APPROVED')),
    ('exception_without_rule',
     (SELECT count(*) FROM legal.legal_exceptions WHERE rule_version_id IS NULL)),
    ('approval_without_rule',
     (SELECT count(*) FROM legal.approvals WHERE rule_version_id IS NULL)),
    ('filing_without_trigger',
     (SELECT count(*) FROM legal.filings WHERE trigger_event IS NULL)),
    ('deadline_without_anchor',
     (SELECT count(*) FROM legal.filing_deadlines WHERE anchor_event IS NULL)),
    ('calculation_without_inputs',
     (SELECT count(*) FROM calc.calculation_versions WHERE jsonb_array_length(required_inputs) = 0)),
    -- A ZIP archive is retained as evidence but has no text of its own; its
    -- members are inventoried and extracted separately. A superseded edition is
    -- likewise catalogued without being extracted: it is kept so the Legal
    -- Library can show what an earlier edition said and link to it at the
    -- regulator, not so it can be cited.
    ('source_without_document',
     (SELECT count(*) FROM legal.legal_sources s
       WHERE s.scope = 'COMPANY' AND s.document_type <> 'CONTAINER'
         AND s.status = 'ACTIVE'
         AND NOT EXISTS (SELECT 1 FROM legal.legal_documents d WHERE d.source_id = s.source_id))),
    ('provision_page_out_of_range',
     (SELECT count(*) FROM legal.legal_provisions p JOIN legal.legal_documents d USING (document_id)
       WHERE p.page_from > d.page_count)),
    ('open_conflicts',
     (SELECT count(*) FROM legal.legal_conflicts WHERE status = 'OPEN')),
    -- An approved rule resting on an edition that has since been replaced. The
    -- rule is not necessarily wrong, but nobody has checked it against the text
    -- that is now in force, and it must not stay in production unreviewed.
    ('approved_rule_on_superseded_source',
     (SELECT count(*) FROM legal.legal_rule_versions rv
        JOIN legal.legal_sources s ON s.source_id = rv.source_id
       WHERE rv.legal_review_status = 'APPROVED' AND s.status = 'SUPERSEDED')),
    -- A superseded edition whose successor is not itself in force means the
    -- chain was built wrongly and the family has no current edition at all.
    ('supersession_chain_broken',
     (SELECT count(*) FROM legal.legal_sources s
        JOIN legal.legal_sources succ ON succ.source_id = s.superseded_by
       WHERE s.status = 'SUPERSEDED' AND succ.status <> 'ACTIVE'))
) AS t(check_name, failing_rows);
COMMENT ON VIEW legal.v_quality_checks IS
  'Brief §27 checks. Every row must read 0 before the rule set goes to production.';

COMMIT;

-- rollback:
--   DROP TRIGGER IF EXISTS superseded_needs_successor ON legal.legal_sources;
--   DROP FUNCTION IF EXISTS legal.assert_supersession_complete();
--   DROP INDEX IF EXISTS legal.legal_sources_document_family_publication_date_idx;
--   DROP INDEX IF EXISTS legal.legal_sources_status_idx;
--   ALTER TABLE legal.legal_sources
--     DROP CONSTRAINT IF EXISTS supersession_basis_known,
--     DROP CONSTRAINT IF EXISTS status_known,
--     DROP CONSTRAINT IF EXISTS superseded_needs_basis,
--     DROP CONSTRAINT IF EXISTS not_superseded_by_itself,
--     DROP COLUMN IF EXISTS document_family,
--     DROP COLUMN IF EXISTS superseded_by,
--     DROP COLUMN IF EXISTS supersession_basis;
--   -- then re-apply the v_quality_checks definition from 006.
