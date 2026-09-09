-- 005 - Calculation, exchange, company and assessment layers (brief §16, §22, §23)

BEGIN;

-- =========================================================== CALCULATIONS (§16)
-- Deliberately separate from legal rules: a rule says "this condition applies",
-- a calculation says "compute X by formula Y". They are linked, never merged.
CREATE TABLE calc.calculations (
    calculation_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    calc_code      text NOT NULL UNIQUE,
    name           text NOT NULL,
    description    text,
    issue_type     legal.issue_type NOT NULL DEFAULT 'GENERAL',
    output_name    text NOT NULL,
    output_unit    text NOT NULL,
    created_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE calc.calculation_versions (
    calculation_version_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    calculation_id uuid NOT NULL REFERENCES calc.calculations(calculation_id) ON DELETE CASCADE,
    version_no     integer NOT NULL CHECK (version_no >= 1),
    formula        text NOT NULL,
    formula_ast    jsonb,
    -- Every input the formula needs, named and typed, so the engine can refuse
    -- to run on incomplete data rather than assume a value (brief §27).
    required_inputs jsonb NOT NULL,
    rounding_mode  text NOT NULL DEFAULT 'HALF_UP'
                   CHECK (rounding_mode IN ('HALF_UP','HALF_EVEN','FLOOR','CEILING','NONE')),
    decimal_places integer CHECK (decimal_places IS NULL OR decimal_places BETWEEN 0 AND 10),
    rule_version_id uuid REFERENCES legal.legal_rule_versions(rule_version_id) ON DELETE SET NULL,
    source_id      uuid NOT NULL REFERENCES legal.legal_sources(source_id) ON DELETE RESTRICT,
    provision_id   uuid REFERENCES legal.legal_provisions(provision_id) ON DELETE RESTRICT,
    source_reference text NOT NULL,
    source_page    integer,
    effective_from date NOT NULL,
    effective_to   date,
    validity       daterange GENERATED ALWAYS AS
                     (daterange(effective_from, effective_to, '[)')) STORED,
    review_status  legal.review_status NOT NULL DEFAULT 'PENDING',
    reviewer_id    text,
    reviewed_at    timestamptz,
    UNIQUE (calculation_id, version_no),
    CONSTRAINT calc_dates_ordered CHECK (effective_to IS NULL OR effective_to > effective_from),
    CONSTRAINT calc_inputs_is_array CHECK (jsonb_typeof(required_inputs) = 'array'),
    CONSTRAINT calc_inputs_not_empty CHECK (jsonb_array_length(required_inputs) >= 1),
    CONSTRAINT calc_approved_needs_reviewer
        CHECK (review_status <> 'APPROVED' OR (reviewer_id IS NOT NULL AND reviewed_at IS NOT NULL))
);
ALTER TABLE calc.calculation_versions
    ADD CONSTRAINT calc_versions_do_not_overlap
    EXCLUDE USING gist (calculation_id WITH =, validity WITH &&);

-- ============================================================== EXCHANGE LAYER
-- Keyed by exchange so BSE gaps show as missing rows rather than being hidden
-- behind NSE defaults.
CREATE TABLE legal.exchange_rules (
    exchange_rule_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    exchange       legal.exchange NOT NULL,
    issue_type     legal.issue_type NOT NULL,
    stage          legal.compliance_stage NOT NULL,
    name           text NOT NULL,
    requirement    text NOT NULL,
    rule_version_id uuid REFERENCES legal.legal_rule_versions(rule_version_id) ON DELETE SET NULL,
    source_id      uuid NOT NULL REFERENCES legal.legal_sources(source_id) ON DELETE RESTRICT,
    provision_id   uuid REFERENCES legal.legal_provisions(provision_id) ON DELETE RESTRICT,
    source_reference text NOT NULL,
    effective_from date NOT NULL,
    effective_to   date,
    review_status  legal.review_status NOT NULL DEFAULT 'PENDING'
);

CREATE TABLE legal.exchange_requirements (
    exchange_requirement_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    exchange_rule_id uuid REFERENCES legal.exchange_rules(exchange_rule_id) ON DELETE CASCADE,
    exchange       legal.exchange NOT NULL,
    issue_type     legal.issue_type NOT NULL,
    stage          legal.compliance_stage NOT NULL,
    item_no        text,
    description    text NOT NULL,
    necessity      legal.requirement_necessity NOT NULL DEFAULT 'MANDATORY',
    doc_requirement_id uuid REFERENCES legal.document_requirements(doc_requirement_id) ON DELETE SET NULL,
    source_id      uuid NOT NULL REFERENCES legal.legal_sources(source_id) ON DELETE RESTRICT,
    source_table_id uuid REFERENCES legal.document_tables(table_id) ON DELETE SET NULL,
    source_reference text NOT NULL,
    review_status  legal.review_status NOT NULL DEFAULT 'PENDING'
);

CREATE TABLE legal.exchange_filings (
    exchange_filing_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    exchange       legal.exchange NOT NULL,
    issue_type     legal.issue_type NOT NULL,
    filing_name    text NOT NULL,
    submission_mode text,                    -- NEAPS, BSE Listing Centre
    trigger_event  text NOT NULL REFERENCES legal.anchor_events(anchor_event),
    filing_id      uuid REFERENCES legal.filings(filing_id) ON DELETE SET NULL,
    source_id      uuid NOT NULL REFERENCES legal.legal_sources(source_id) ON DELETE RESTRICT,
    source_reference text NOT NULL,
    effective_from date NOT NULL,
    effective_to   date,
    review_status  legal.review_status NOT NULL DEFAULT 'PENDING'
);

CREATE TABLE legal.exchange_deadlines (
    exchange_deadline_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    exchange_filing_id uuid REFERENCES legal.exchange_filings(exchange_filing_id) ON DELETE CASCADE,
    exchange       legal.exchange NOT NULL,
    issue_type     legal.issue_type NOT NULL,
    anchor_event   text NOT NULL REFERENCES legal.anchor_events(anchor_event),
    direction      legal.deadline_direction NOT NULL DEFAULT 'AFTER',
    offset_value   integer NOT NULL CHECK (offset_value >= 0),
    offset_unit    text NOT NULL DEFAULT 'DAYS' CHECK (offset_unit IN ('DAYS','MONTHS','YEARS')),
    day_type       legal.day_type NOT NULL DEFAULT 'WORKING',
    description    text NOT NULL,
    source_id      uuid NOT NULL REFERENCES legal.legal_sources(source_id) ON DELETE RESTRICT,
    source_reference text NOT NULL,
    review_status  legal.review_status NOT NULL DEFAULT 'PENDING'
);

-- ======================================================== COMPANY FACTS (§22)
CREATE TABLE company.companies (
    company_id  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    cin         text UNIQUE,
    name        text NOT NULL,
    incorporation_date date,
    registered_state text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT cin_shape CHECK (cin IS NULL OR cin ~ '^[LUu][0-9]{5}[A-Za-z]{2}[0-9]{4}[A-Za-z]{3}[0-9]{6}$')
);

CREATE TABLE company.company_classifications (
    classification_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id    uuid NOT NULL REFERENCES company.companies(company_id) ON DELETE CASCADE,
    company_type  legal.company_type NOT NULL,
    listed_status legal.listed_status NOT NULL,
    exchanges     legal.exchange[] NOT NULL DEFAULT '{}',
    is_sme        boolean NOT NULL DEFAULT false,
    effective_from date NOT NULL,
    effective_to  date,
    validity      daterange GENERATED ALWAYS AS
                    (daterange(effective_from, effective_to, '[)')) STORED,
    CONSTRAINT classification_dates_ordered CHECK (effective_to IS NULL OR effective_to > effective_from)
);
ALTER TABLE company.company_classifications
    ADD CONSTRAINT classification_no_overlap
    EXCLUDE USING gist (company_id WITH =, validity WITH &&);

CREATE TABLE company.share_classes (
    share_class_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id  uuid NOT NULL REFERENCES company.companies(company_id) ON DELETE CASCADE,
    name        text NOT NULL,
    security_type legal.security_type NOT NULL,
    face_value  numeric(18,4) NOT NULL CHECK (face_value > 0),
    votes_per_share numeric(10,4) NOT NULL DEFAULT 1,
    UNIQUE (company_id, name)
);

CREATE TABLE company.capital_snapshots (
    snapshot_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id  uuid NOT NULL REFERENCES company.companies(company_id) ON DELETE CASCADE,
    share_class_id uuid REFERENCES company.share_classes(share_class_id) ON DELETE SET NULL,
    as_of_date  date NOT NULL,
    authorised_capital numeric(20,2) NOT NULL CHECK (authorised_capital >= 0),
    issued_capital     numeric(20,2) NOT NULL CHECK (issued_capital >= 0),
    subscribed_capital numeric(20,2) NOT NULL CHECK (subscribed_capital >= 0),
    paid_up_capital    numeric(20,2) NOT NULL CHECK (paid_up_capital >= 0),
    face_value         numeric(18,4) NOT NULL CHECK (face_value > 0),
    shares_issued      numeric(20,4) NOT NULL CHECK (shares_issued >= 0),
    -- Capital cannot exceed its own ceiling; this is arithmetic, not law.
    CONSTRAINT issued_within_authorised   CHECK (issued_capital <= authorised_capital),
    CONSTRAINT subscribed_within_issued   CHECK (subscribed_capital <= issued_capital),
    CONSTRAINT paidup_within_subscribed   CHECK (paid_up_capital <= subscribed_capital),
    UNIQUE (company_id, share_class_id, as_of_date)
);

CREATE TABLE company.shareholders (
    shareholder_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id  uuid NOT NULL REFERENCES company.companies(company_id) ON DELETE CASCADE,
    name        text NOT NULL,
    pan         text,
    category    text NOT NULL DEFAULT 'PUBLIC',
    is_promoter boolean NOT NULL DEFAULT false,
    is_promoter_group boolean NOT NULL DEFAULT false,
    is_qib      boolean NOT NULL DEFAULT false,
    is_related_party boolean NOT NULL DEFAULT false,
    demat_holding boolean
);

CREATE TABLE company.holdings (
    holding_id  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    shareholder_id uuid NOT NULL REFERENCES company.shareholders(shareholder_id) ON DELETE CASCADE,
    share_class_id uuid NOT NULL REFERENCES company.share_classes(share_class_id) ON DELETE CASCADE,
    as_of_date  date NOT NULL,
    shares_held numeric(20,4) NOT NULL CHECK (shares_held >= 0),
    locked_in_shares numeric(20,4) NOT NULL DEFAULT 0 CHECK (locked_in_shares >= 0),
    lock_in_until date,
    CONSTRAINT lockin_within_holding CHECK (locked_in_shares <= shares_held),
    UNIQUE (shareholder_id, share_class_id, as_of_date)
);

CREATE TABLE company.securities (
    security_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id  uuid NOT NULL REFERENCES company.companies(company_id) ON DELETE CASCADE,
    isin        text,
    security_type legal.security_type NOT NULL,
    share_class_id uuid REFERENCES company.share_classes(share_class_id) ON DELETE SET NULL,
    description text
);

CREATE TABLE company.security_terms (
    security_term_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    security_id uuid NOT NULL REFERENCES company.securities(security_id) ON DELETE CASCADE,
    tenure_months integer CHECK (tenure_months IS NULL OR tenure_months > 0),
    coupon_rate numeric(8,4),
    conversion_ratio numeric(18,8),
    conversion_price numeric(18,4),
    is_convertible boolean NOT NULL DEFAULT false,
    terms jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE company.security_conversions (
    conversion_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    security_id uuid NOT NULL REFERENCES company.securities(security_id) ON DELETE CASCADE,
    conversion_date date NOT NULL,
    securities_converted numeric(20,4) NOT NULL CHECK (securities_converted > 0),
    shares_issued numeric(20,4) NOT NULL CHECK (shares_issued > 0),
    conversion_price numeric(18,4)
);

CREATE TABLE company.issues (
    issue_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id  uuid NOT NULL REFERENCES company.companies(company_id) ON DELETE CASCADE,
    issue_type  legal.issue_type NOT NULL,
    security_type legal.security_type NOT NULL,
    share_class_id uuid REFERENCES company.share_classes(share_class_id) ON DELETE SET NULL,
    announcement_date date,
    board_resolution_date date,
    shareholder_resolution_date date,
    relevant_date date,
    record_date date,
    issue_open_date date,
    issue_close_date date,
    allotment_date date,
    shares_offered numeric(20,4) CHECK (shares_offered IS NULL OR shares_offered > 0),
    issue_price numeric(18,4) CHECK (issue_price IS NULL OR issue_price >= 0),
    premium_per_share numeric(18,4),
    total_consideration numeric(20,2),
    rights_ratio_num integer CHECK (rights_ratio_num IS NULL OR rights_ratio_num > 0),
    rights_ratio_den integer CHECK (rights_ratio_den IS NULL OR rights_ratio_den > 0),
    status text NOT NULL DEFAULT 'PLANNED',
    CONSTRAINT issue_dates_sane CHECK (
        (issue_close_date IS NULL OR issue_open_date IS NULL OR issue_close_date >= issue_open_date)
        AND (allotment_date IS NULL OR issue_close_date IS NULL OR allotment_date >= issue_close_date))
);

CREATE TABLE company.issue_allottees (
    allottee_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    issue_id    uuid NOT NULL REFERENCES company.issues(issue_id) ON DELETE CASCADE,
    shareholder_id uuid REFERENCES company.shareholders(shareholder_id) ON DELETE SET NULL,
    name        text NOT NULL,
    pan         text,
    category    text,
    shares_allotted numeric(20,4) NOT NULL CHECK (shares_allotted > 0),
    price_per_share numeric(18,4),
    lock_in_until date,
    pre_issue_holding numeric(20,4) NOT NULL DEFAULT 0
);

-- ======================================================== ASSESSMENTS (§23)
CREATE TABLE assess.scenarios (
    scenario_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id  uuid NOT NULL REFERENCES company.companies(company_id) ON DELETE CASCADE,
    issue_id    uuid REFERENCES company.issues(issue_id) ON DELETE SET NULL,
    name        text NOT NULL,
    issue_type  legal.issue_type NOT NULL,
    transaction_date date NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);
COMMENT ON COLUMN assess.scenarios.transaction_date IS
  'Selects which rule and calculation versions apply. Not the run date.';

CREATE TABLE assess.scenario_inputs (
    scenario_input_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    scenario_id uuid NOT NULL REFERENCES assess.scenarios(scenario_id) ON DELETE CASCADE,
    key   text NOT NULL,
    value jsonb NOT NULL,
    source text NOT NULL DEFAULT 'USER',
    UNIQUE (scenario_id, key)
);

CREATE TABLE assess.assessment_results (
    assessment_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    scenario_id uuid NOT NULL REFERENCES assess.scenarios(scenario_id) ON DELETE CASCADE,
    run_at      timestamptz NOT NULL DEFAULT now(),
    engine_version text NOT NULL,
    overall_result legal.rule_result NOT NULL,
    rules_evaluated integer NOT NULL DEFAULT 0,
    blocks_count    integer NOT NULL DEFAULT 0,
    warnings_count  integer NOT NULL DEFAULT 0,
    review_count    integer NOT NULL DEFAULT 0,
    assumptions  jsonb NOT NULL DEFAULT '[]'::jsonb,
    inputs_snapshot jsonb NOT NULL,
    notes text
);
COMMENT ON COLUMN assess.assessment_results.inputs_snapshot IS
  'Frozen copy of the inputs, so a past assessment stays reproducible.';

CREATE TABLE assess.assessment_rule_results (
    assessment_rule_result_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    assessment_id uuid NOT NULL REFERENCES assess.assessment_results(assessment_id) ON DELETE CASCADE,
    -- Pin the exact version used; the law may change afterwards (brief §23).
    rule_version_id uuid NOT NULL REFERENCES legal.legal_rule_versions(rule_version_id) ON DELETE RESTRICT,
    status      legal.rule_result NOT NULL,
    message     text NOT NULL,
    explanation text,
    condition_trace jsonb NOT NULL DEFAULT '{}'::jsonb,
    exception_applied uuid REFERENCES legal.legal_exceptions(exception_id) ON DELETE SET NULL,
    source_reference text NOT NULL,
    source_page integer,
    UNIQUE (assessment_id, rule_version_id)
);
COMMENT ON COLUMN assess.assessment_rule_results.condition_trace IS
  'Per-node evaluation trace: why the rule produced this result (brief §24).';

CREATE TABLE assess.assessment_calculations (
    assessment_calc_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    assessment_id uuid NOT NULL REFERENCES assess.assessment_results(assessment_id) ON DELETE CASCADE,
    calculation_version_id uuid NOT NULL
        REFERENCES calc.calculation_versions(calculation_version_id) ON DELETE RESTRICT,
    inputs  jsonb NOT NULL,
    formula text NOT NULL,
    result  numeric(24,6),
    result_text text,
    unit    text NOT NULL,
    UNIQUE (assessment_id, calculation_version_id)
);

COMMIT;

-- rollback:
--   DROP TABLE IF EXISTS assess.assessment_calculations, assess.assessment_rule_results,
--     assess.assessment_results, assess.scenario_inputs, assess.scenarios,
--     company.issue_allottees, company.issues, company.security_conversions,
--     company.security_terms, company.securities, company.holdings,
--     company.shareholders, company.capital_snapshots, company.share_classes,
--     company.company_classifications, company.companies,
--     legal.exchange_deadlines, legal.exchange_filings, legal.exchange_requirements,
--     legal.exchange_rules, calc.calculation_versions, calc.calculations CASCADE;
