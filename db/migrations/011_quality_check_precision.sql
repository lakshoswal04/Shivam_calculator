-- 011 - Separate "rule has no anchor" from "rule's printed citation recurs"
--
-- The original check flagged any rule whose provision carries
-- citation_ambiguous. That conflates two different problems:
--
--   * a rule with no provision_id at all -- it cannot be traced, which is a
--     hard failure; and
--   * a rule anchored exactly by provision_id whose human-readable citation
--     string happens to recur elsewhere in the instrument (Schedules restart
--     numbering, and some regulations repeat a sub-numbering). The anchor is
--     exact and the drill-down lands on the right text; only a reader typing
--     the citation into a PDF could go astray.
--
-- Reporting the second as a failure would train people to ignore the check.
-- It is kept as its own advisory line instead.

BEGIN;

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
    ('source_without_document',
     (SELECT count(*) FROM legal.legal_sources s
       WHERE s.scope = 'COMPANY' AND s.document_type <> 'CONTAINER'
         AND NOT EXISTS (SELECT 1 FROM legal.legal_documents d WHERE d.source_id = s.source_id))),
    ('provision_page_out_of_range',
     (SELECT count(*) FROM legal.legal_provisions p JOIN legal.legal_documents d USING (document_id)
       WHERE p.page_from > d.page_count)),
    ('open_conflicts',
     (SELECT count(*) FROM legal.legal_conflicts WHERE status = 'OPEN'))
) AS t(check_name, failing_rows);

-- Advisory, not a gate: the anchor is exact, the printed citation is not unique.
CREATE VIEW legal.v_citation_advisories AS
SELECT r.rule_code, rv.rule_version_id, p.citation, p.citation_uid, p.page_from,
       (SELECT count(*) FROM legal.legal_provisions x
         WHERE x.instrument_id = p.instrument_id AND x.citation = p.citation) AS occurrences
FROM legal.legal_rule_versions rv
JOIN legal.legal_rules r USING (rule_id)
JOIN legal.legal_provisions p ON p.provision_id = rv.provision_id
WHERE p.citation_ambiguous;
COMMENT ON VIEW legal.v_citation_advisories IS
  'Rules anchored exactly by provision_id whose printed citation recurs in the instrument.';

COMMIT;

-- rollback: see 006 for the previous definition of legal.v_quality_checks;
--   DROP VIEW IF EXISTS legal.v_citation_advisories;
