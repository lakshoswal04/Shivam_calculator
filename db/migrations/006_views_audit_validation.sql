-- 006 - Compatibility views, production gate, audit trail, validation (brief §19-§27)

BEGIN;

-- ============================ COMPATIBILITY VIEWS OVER legal_provisions (§21)
-- The brief names legal_sections / legal_regulations / legal_clauses. They are
-- projections of one recursive table, because Indian citations nest to
-- arbitrary depth (s.62(1)(a)(ii) + proviso) which fixed tables cannot express.
CREATE VIEW legal.legal_sections AS
    SELECT provision_id AS section_id, document_id, instrument_id, parent_id,
           number AS section_number, heading, citation, citation_uid,
           page_from, page_to, body_text, amended, amendment_markers
    FROM legal.legal_provisions WHERE provision_type = 'SECTION';

CREATE VIEW legal.legal_regulations AS
    SELECT provision_id AS regulation_id, document_id, instrument_id, parent_id,
           number AS regulation_number, heading, citation, citation_uid,
           page_from, page_to, body_text, amended, amendment_markers
    FROM legal.legal_provisions WHERE provision_type = 'REGULATION';

CREATE VIEW legal.legal_clauses AS
    SELECT provision_id AS clause_id, document_id, instrument_id, parent_id,
           provision_type, number AS clause_number, heading, citation, citation_uid,
           page_from, page_to, body_text, amended, amendment_markers
    FROM legal.legal_provisions
    WHERE provision_type IN ('SUB_SECTION','SUB_RULE','SUB_REGULATION',
                             'CLAUSE','SUB_CLAUSE','PROVISO','EXPLANATION');

-- Full ancestry of a provision, for rendering a citation trail.
CREATE VIEW legal.v_provision_ancestry AS
WITH RECURSIVE up AS (
    SELECT provision_id, parent_id, citation, provision_id AS leaf_id, 0 AS lvl
    FROM legal.legal_provisions
  UNION ALL
    SELECT p.provision_id, p.parent_id, p.citation, up.leaf_id, up.lvl + 1
    FROM legal.legal_provisions p JOIN up ON up.parent_id = p.provision_id
)
SELECT leaf_id AS provision_id, array_agg(citation ORDER BY lvl DESC) AS ancestry
FROM up GROUP BY leaf_id;

-- ===================================================== PRODUCTION GATE (§19,§26)
-- The rule engine reads ONLY this view. A rule reaches production solely by
-- human approval, inside its validity window, with no unresolved conflict.
CREATE VIEW legal.v_active_rule_versions AS
    SELECT rv.*, r.rule_code, r.title AS rule_title
    FROM legal.legal_rule_versions rv
    JOIN legal.legal_rules r USING (rule_id)
    WHERE rv.legal_review_status = 'APPROVED'
      AND rv.human_review_required = false
      AND rv.conflict_detected = false
      AND NOT EXISTS (
            SELECT 1 FROM legal.legal_conflicts c
            WHERE c.rule_id = r.rule_id AND c.status IN ('OPEN','UNDER_REVIEW'));
COMMENT ON VIEW legal.v_active_rule_versions IS
  'Production rule set. Never query legal_rule_versions directly from the engine.';

CREATE FUNCTION legal.rules_in_force(p_on_date date)
RETURNS SETOF legal.v_active_rule_versions
LANGUAGE sql STABLE AS $$
    SELECT * FROM legal.v_active_rule_versions WHERE validity @> p_on_date;
$$;
COMMENT ON FUNCTION legal.rules_in_force(date) IS
  'Rules applicable to a transaction date - the version selector required by brief §17.';

CREATE VIEW calc.v_active_calculation_versions AS
    SELECT cv.*, c.calc_code, c.name AS calc_name, c.output_name, c.output_unit
    FROM calc.calculation_versions cv
    JOIN calc.calculations c USING (calculation_id)
    WHERE cv.review_status = 'APPROVED';

-- ======================================================== DEADLINE ARITHMETIC (§15)
-- Deadlines are computed from an anchor, never stored as a fixed date.
CREATE FUNCTION legal.add_days(p_anchor date, p_offset integer, p_day_type legal.day_type)
RETURNS date LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE d date := p_anchor; remaining integer := p_offset;
BEGIN
    IF p_day_type = 'CALENDAR' THEN
        RETURN p_anchor + p_offset;
    END IF;
    -- WORKING and TRADING both skip weekends here. TRADING additionally depends
    -- on the exchange holiday calendar, which is not in this database; callers
    -- must treat a TRADING result as provisional until that calendar exists.
    WHILE remaining > 0 LOOP
        d := d + 1;
        IF extract(isodow FROM d) < 6 THEN remaining := remaining - 1; END IF;
    END LOOP;
    RETURN d;
END $$;

CREATE FUNCTION legal.compute_deadline(
    p_anchor date, p_offset integer, p_unit text,
    p_day_type legal.day_type, p_direction legal.deadline_direction)
RETURNS date LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE signed integer;
BEGIN
    IF p_direction = 'ON' THEN RETURN p_anchor; END IF;
    signed := CASE WHEN p_direction = 'BEFORE' THEN -p_offset ELSE p_offset END;
    IF p_unit = 'MONTHS' THEN RETURN p_anchor + (signed || ' months')::interval;
    ELSIF p_unit = 'YEARS' THEN RETURN p_anchor + (signed || ' years')::interval;
    END IF;
    IF p_direction = 'BEFORE' AND p_day_type <> 'CALENDAR' THEN
        RETURN NULL;   -- backwards working-day counts need the holiday calendar
    END IF;
    RETURN legal.add_days(p_anchor, signed, p_day_type);
END $$;

-- ============================================================ AUDIT TRAIL (§21)
CREATE TABLE audit.rule_change_log (
    change_id   bigserial PRIMARY KEY,
    table_name  text NOT NULL,
    row_pk      uuid NOT NULL,
    action      text NOT NULL CHECK (action IN ('INSERT','UPDATE','DELETE')),
    old_row     jsonb,
    new_row     jsonb,
    changed_by  text NOT NULL DEFAULT current_user,
    changed_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON audit.rule_change_log (table_name, row_pk);

CREATE TABLE audit.audit_logs (
    log_id     bigserial PRIMARY KEY,
    event      text NOT NULL,
    detail     jsonb NOT NULL DEFAULT '{}'::jsonb,
    actor      text NOT NULL DEFAULT current_user,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE FUNCTION audit.log_change() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE pk uuid;
BEGIN
    pk := COALESCE(
        (to_jsonb(NEW) ->> TG_ARGV[0])::uuid,
        (to_jsonb(OLD) ->> TG_ARGV[0])::uuid);
    INSERT INTO audit.rule_change_log (table_name, row_pk, action, old_row, new_row)
    VALUES (TG_TABLE_SCHEMA || '.' || TG_TABLE_NAME, pk, TG_OP,
            CASE WHEN TG_OP <> 'INSERT' THEN to_jsonb(OLD) END,
            CASE WHEN TG_OP <> 'DELETE' THEN to_jsonb(NEW) END);
    RETURN COALESCE(NEW, OLD);
END $$;

CREATE TRIGGER trg_audit_rule_versions
    AFTER INSERT OR UPDATE OR DELETE ON legal.legal_rule_versions
    FOR EACH ROW EXECUTE FUNCTION audit.log_change('rule_version_id');
CREATE TRIGGER trg_audit_calc_versions
    AFTER INSERT OR UPDATE OR DELETE ON calc.calculation_versions
    FOR EACH ROW EXECUTE FUNCTION audit.log_change('calculation_version_id');
CREATE TRIGGER trg_audit_exceptions
    AFTER INSERT OR UPDATE OR DELETE ON legal.legal_exceptions
    FOR EACH ROW EXECUTE FUNCTION audit.log_change('exception_id');

-- ============================================ SOURCE PRIORITY ENFORCEMENT (§18)
-- A production rule may not rest on secondary material (P3) or the open web (P4).
CREATE FUNCTION legal.enforce_source_priority() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE prio legal.source_priority; cons legal.consolidation_status;
BEGIN
    SELECT source_priority, consolidation_status INTO prio, cons
    FROM legal.legal_sources WHERE source_id = NEW.source_id;
    IF NEW.legal_review_status = 'APPROVED' AND prio IN ('P3','P4') THEN
        RAISE EXCEPTION
          'Rule version % cannot be APPROVED: source priority % is not admissible for production (brief §18)',
          NEW.rule_version_id, prio;
    END IF;
    IF NEW.legal_review_status = 'APPROVED' AND cons = 'REFERENCE_ONLY' THEN
        RAISE EXCEPTION
          'Rule version % cannot be APPROVED: source is REFERENCE_ONLY and does not carry later amendments',
          NEW.rule_version_id;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER trg_enforce_source_priority
    BEFORE INSERT OR UPDATE ON legal.legal_rule_versions
    FOR EACH ROW EXECUTE FUNCTION legal.enforce_source_priority();

-- ============================================================ CONDITION AST (§10)
CREATE FUNCTION legal.validate_condition_ast(node jsonb)
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
    END IF;
    RETURN false;
END $$;

ALTER TABLE legal.legal_conditions
    ADD CONSTRAINT condition_ast_valid CHECK (legal.validate_condition_ast(expr_json));
ALTER TABLE legal.legal_exceptions
    ADD CONSTRAINT exception_ast_valid CHECK (legal.validate_condition_ast(expr_json));
ALTER TABLE legal.approval_conditions
    ADD CONSTRAINT approval_ast_valid CHECK (legal.validate_condition_ast(expr_json));

-- ========================================================== QUALITY CHECKS (§27)
CREATE VIEW legal.v_quality_checks AS
SELECT * FROM (
  VALUES
    ('rule_without_source',
     (SELECT count(*) FROM legal.legal_rule_versions WHERE source_id IS NULL)),
    ('rule_without_provision',
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
    -- members are inventoried and extracted separately.
    ('source_without_document',
     (SELECT count(*) FROM legal.legal_sources s
       WHERE s.scope = 'COMPANY' AND s.document_type <> 'CONTAINER'
         AND NOT EXISTS (SELECT 1 FROM legal.legal_documents d WHERE d.source_id = s.source_id))),
    ('provision_page_out_of_range',
     (SELECT count(*) FROM legal.legal_provisions p JOIN legal.legal_documents d USING (document_id)
       WHERE p.page_from > d.page_count)),
    ('ambiguous_citation_used_by_rule',
     (SELECT count(*) FROM legal.legal_rule_versions rv
        JOIN legal.legal_provisions p ON p.provision_id = rv.provision_id
       WHERE p.citation_ambiguous)),
    ('open_conflicts',
     (SELECT count(*) FROM legal.legal_conflicts WHERE status = 'OPEN'))
) AS t(check_name, failing_rows);
COMMENT ON VIEW legal.v_quality_checks IS
  'Brief §27 checks. Every row must read 0 before the rule set goes to production.';

COMMIT;

-- rollback:
--   DROP VIEW IF EXISTS legal.v_quality_checks, calc.v_active_calculation_versions,
--     legal.v_active_rule_versions, legal.v_provision_ancestry,
--     legal.legal_clauses, legal.legal_regulations, legal.legal_sections CASCADE;
--   DROP TABLE IF EXISTS audit.audit_logs, audit.rule_change_log CASCADE;
