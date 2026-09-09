-- 003 - Rule layer (brief §8, §9, §10, §11, §17, §19, §20)
-- Rules are split into a stable identity and immutable, dated versions.
-- Old versions are never overwritten; they are closed off.

BEGIN;

-- ------------------------------------------------------------------ legal_rules
CREATE TABLE legal.legal_rules (
    rule_id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_code   text NOT NULL UNIQUE,          -- 'PREF-001'
    title       text NOT NULL,
    authority   legal.authority NOT NULL,
    issue_type  legal.issue_type NOT NULL,
    description text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT rule_code_shape CHECK (rule_code ~ '^[A-Z][A-Z0-9]{1,15}-[0-9]{3,5}$')
);
COMMENT ON TABLE legal.legal_rules IS 'Stable rule identity only. Everything that can change over time lives in legal_rule_versions.';

-- ---------------------------------------------------------- legal_rule_versions
CREATE TABLE legal.legal_rule_versions (
    rule_version_id  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_id          uuid NOT NULL REFERENCES legal.legal_rules(rule_id) ON DELETE CASCADE,
    version_no       integer NOT NULL CHECK (version_no >= 1),

    -- Applicability, held apart from the legal text (brief §7).
    issue_type       legal.issue_type    NOT NULL,
    company_type     legal.company_type  NOT NULL DEFAULT 'ANY',
    listed_status    legal.listed_status NOT NULL DEFAULT 'UNKNOWN',
    security_type    legal.security_type NOT NULL DEFAULT 'ANY',
    exchange         legal.exchange      NOT NULL DEFAULT 'ANY',

    -- Trigger / requirement / outcome kept in separate columns (brief §9).
    trigger_expr     text NOT NULL,
    requirement      text NOT NULL,
    result_if_pass   legal.rule_result NOT NULL DEFAULT 'PASS',
    result_if_fail   legal.rule_result NOT NULL,
    severity         legal.severity    NOT NULL,
    message_template text,

    -- Provenance: the exact provision this rule was derived from (brief §34).
    source_id        uuid NOT NULL REFERENCES legal.legal_sources(source_id)    ON DELETE RESTRICT,
    provision_id     uuid          REFERENCES legal.legal_provisions(provision_id) ON DELETE RESTRICT,
    source_page      integer CHECK (source_page IS NULL OR source_page >= 1),
    source_reference text NOT NULL,
    source_quote     text,

    -- Temporal validity. NULL upper bound = still in force (brief §17).
    effective_from   date NOT NULL,
    effective_to     date,
    validity         daterange GENERATED ALWAYS AS
                       (daterange(effective_from, effective_to, '[)')) STORED,

    -- Review gate (brief §19, §26).
    legal_review_status   legal.review_status NOT NULL DEFAULT 'PENDING',
    human_review_required boolean NOT NULL DEFAULT true,
    reviewer_id      text,
    reviewed_at      timestamptz,
    review_notes     text,
    conflict_detected boolean NOT NULL DEFAULT false,

    extraction_confidence numeric(3,2) CHECK (extraction_confidence IS NULL
                                              OR extraction_confidence BETWEEN 0 AND 1),
    created_at       timestamptz NOT NULL DEFAULT now(),
    created_by       text NOT NULL DEFAULT 'pipeline',

    UNIQUE (rule_id, version_no),
    CONSTRAINT effective_dates_ordered
        CHECK (effective_to IS NULL OR effective_to > effective_from),
    -- A rule may only rest on primary law, official regulatory material or
    -- official operational requirements (brief §18).
    CONSTRAINT approved_needs_reviewer
        CHECK (legal_review_status <> 'APPROVED'
               OR (reviewer_id IS NOT NULL AND reviewed_at IS NOT NULL)),
    CONSTRAINT approved_is_not_flagged
        CHECK (legal_review_status <> 'APPROVED' OR human_review_required = false)
);

-- The database itself refuses to hold two versions of one rule covering the
-- same date. Version overlap is a correctness bug, not a data-quality warning.
ALTER TABLE legal.legal_rule_versions
    ADD CONSTRAINT rule_versions_do_not_overlap
    EXCLUDE USING gist (rule_id WITH =, validity WITH &&);

CREATE INDEX ON legal.legal_rule_versions (rule_id);
CREATE INDEX ON legal.legal_rule_versions (legal_review_status);
CREATE INDEX ON legal.legal_rule_versions (issue_type, company_type, listed_status);
CREATE INDEX rule_versions_validity_gist ON legal.legal_rule_versions USING gist (validity);
CREATE INDEX ON legal.legal_rule_versions (source_id);

COMMENT ON COLUMN legal.legal_rule_versions.validity IS
  'Half-open [from,to) range; the engine selects the version covering the transaction date.';

-- ------------------------------------------------------------- legal_conditions
-- Machine-readable condition AST (brief §10):
--   {"op":"AND","args":[{"op":"eq","field":"company.listed","value":true}]}
CREATE TABLE legal.legal_conditions (
    condition_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_version_id uuid NOT NULL REFERENCES legal.legal_rule_versions(rule_version_id) ON DELETE CASCADE,
    condition_role  text NOT NULL DEFAULT 'CONDITION'
                    CHECK (condition_role IN ('TRIGGER','CONDITION','REQUIREMENT_TEST')),
    expr_json       jsonb NOT NULL,
    expr_text       text  NOT NULL,
    ordinal         integer NOT NULL DEFAULT 1,
    notes           text,
    UNIQUE (rule_version_id, condition_role, ordinal),
    -- Shape check only; full validation lives in the evaluator (006).
    CONSTRAINT expr_is_object CHECK (jsonb_typeof(expr_json) = 'object'),
    CONSTRAINT expr_has_op    CHECK (expr_json ? 'op'),
    CONSTRAINT expr_op_known  CHECK (expr_json ->> 'op' IN
        ('AND','OR','NOT','eq','ne','gt','gte','lt','lte','in','not_in','exists','not_exists'))
);
COMMENT ON TABLE legal.legal_conditions IS
  'Conditions as an evaluable AST plus a human-readable mirror. Never free text alone.';

-- ------------------------------------------------------------- legal_exceptions
-- Exceptions carry their own condition and their own validity, and the engine
-- evaluates them AFTER conditions and before emitting a result (brief §11).
CREATE TABLE legal.legal_exceptions (
    exception_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_version_id uuid NOT NULL REFERENCES legal.legal_rule_versions(rule_version_id) ON DELETE CASCADE,
    exception_code  text NOT NULL,
    description     text NOT NULL,
    expr_json       jsonb NOT NULL,
    expr_text       text  NOT NULL,
    effect          legal.rule_result NOT NULL DEFAULT 'NOT_APPLICABLE',
    source_id       uuid NOT NULL REFERENCES legal.legal_sources(source_id) ON DELETE RESTRICT,
    provision_id    uuid REFERENCES legal.legal_provisions(provision_id) ON DELETE RESTRICT,
    source_page     integer,
    source_reference text NOT NULL,
    effective_from  date NOT NULL,
    effective_to    date,
    review_status   legal.review_status NOT NULL DEFAULT 'PENDING',
    UNIQUE (rule_version_id, exception_code),
    CONSTRAINT exception_dates_ordered CHECK (effective_to IS NULL OR effective_to > effective_from),
    CONSTRAINT exception_expr_is_object CHECK (jsonb_typeof(expr_json) = 'object')
);

-- ----------------------------------------------------------- legal_requirements
CREATE TABLE legal.legal_requirements (
    requirement_id  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_version_id uuid NOT NULL REFERENCES legal.legal_rule_versions(rule_version_id) ON DELETE CASCADE,
    requirement_text text NOT NULL,
    necessity       legal.requirement_necessity NOT NULL DEFAULT 'MANDATORY',
    stage           legal.compliance_stage,
    ordinal         integer NOT NULL DEFAULT 1,
    UNIQUE (rule_version_id, ordinal)
);

-- -------------------------------------------------------------- legal_conflicts
-- Conflicts are recorded, never auto-resolved. Supersession is not inferred
-- from dates alone (brief §20).
CREATE TABLE legal.legal_conflicts (
    conflict_id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_a_id     uuid NOT NULL REFERENCES legal.legal_sources(source_id) ON DELETE RESTRICT,
    provision_a_id  uuid REFERENCES legal.legal_provisions(provision_id) ON DELETE SET NULL,
    source_b_id     uuid NOT NULL REFERENCES legal.legal_sources(source_id) ON DELETE RESTRICT,
    provision_b_id  uuid REFERENCES legal.legal_provisions(provision_id) ON DELETE SET NULL,
    rule_id         uuid REFERENCES legal.legal_rules(rule_id) ON DELETE SET NULL,
    description     text NOT NULL,
    date_a          date,
    date_b          date,
    status          legal.conflict_status NOT NULL DEFAULT 'OPEN',
    resolution_notes text,
    resolved_by     text,
    resolved_at     timestamptz,
    detected_at     timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT conflict_two_distinct_sources CHECK (source_a_id <> source_b_id
                                                    OR provision_a_id IS DISTINCT FROM provision_b_id),
    CONSTRAINT resolved_needs_reason
        CHECK (status NOT IN ('RESOLVED','NOT_A_CONFLICT')
               OR (resolution_notes IS NOT NULL AND resolved_by IS NOT NULL))
);

COMMIT;

-- rollback:
--   DROP TABLE IF EXISTS legal.legal_conflicts, legal.legal_requirements,
--     legal.legal_exceptions, legal.legal_conditions,
--     legal.legal_rule_versions, legal.legal_rules CASCADE;
