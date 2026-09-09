-- 004 - Compliance layer: approvals, filings, deadlines, documents (brief §12-§15)
-- Deadlines are stored compositionally (anchor event + offset + day type),
-- never as a fixed date, so the engine can compute them for any transaction.

BEGIN;

-- Anchor events a deadline can be measured from (brief §13, §15).
CREATE TABLE legal.anchor_events (
    anchor_event  text PRIMARY KEY,
    description   text NOT NULL,
    stage         legal.compliance_stage NOT NULL
);
INSERT INTO legal.anchor_events (anchor_event, description, stage) VALUES
 ('BOARD_RESOLUTION_DATE',      'Date the board passed the enabling resolution',        'PRE_ISSUE'),
 ('SHAREHOLDER_RESOLUTION_DATE','Date of the general meeting / postal ballot result',   'PRE_ISSUE'),
 ('NOTICE_DISPATCH_DATE',       'Date the notice of the general meeting was dispatched','PRE_ISSUE'),
 ('RELEVANT_DATE',              'Relevant date for pricing under SEBI ICDR',            'PRE_ISSUE'),
 ('OFFER_LETTER_DATE',          'Date the private placement offer letter was circulated','PRE_ALLOTMENT'),
 ('IN_PRINCIPLE_APPROVAL_DATE', 'Date the exchange granted in-principle approval',      'PRE_ALLOTMENT'),
 ('ISSUE_OPEN_DATE',            'Date the issue opened',                               'PRE_ALLOTMENT'),
 ('ISSUE_CLOSE_DATE',           'Date the issue closed',                               'PRE_ALLOTMENT'),
 ('ALLOTMENT_DATE',             'Date of allotment of the securities',                 'ALLOTMENT'),
 ('MONEY_RECEIPT_DATE',         'Date subscription money was received',                'ALLOTMENT'),
 ('LISTING_APPROVAL_DATE',      'Date the exchange granted listing approval',           'LISTING'),
 ('TRADING_APPROVAL_DATE',      'Date the exchange granted trading approval',           'TRADING'),
 ('RECORD_DATE',                'Record date fixed for the corporate action',           'PRE_ISSUE'),
 ('FINANCIAL_YEAR_END',         'End of the relevant financial year',                   'ONGOING');

-- ---------------------------------------------------------------- approvals §12
CREATE TABLE legal.approvals (
    approval_id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    approval_code   text NOT NULL UNIQUE,
    approval_type   legal.approval_type NOT NULL,
    name            text NOT NULL,
    authority       legal.authority NOT NULL,
    issue_type      legal.issue_type NOT NULL,
    company_type    legal.company_type NOT NULL DEFAULT 'ANY',
    listed_status   legal.listed_status NOT NULL DEFAULT 'UNKNOWN',
    exchange        legal.exchange NOT NULL DEFAULT 'ANY',
    stage           legal.compliance_stage NOT NULL,
    -- Every approval must be caused by a rule; approvals are not free text (brief §12).
    rule_version_id uuid NOT NULL REFERENCES legal.legal_rule_versions(rule_version_id) ON DELETE CASCADE,
    source_id       uuid NOT NULL REFERENCES legal.legal_sources(source_id) ON DELETE RESTRICT,
    provision_id    uuid REFERENCES legal.legal_provisions(provision_id) ON DELETE RESTRICT,
    source_reference text NOT NULL,
    source_page     integer,
    effective_from  date NOT NULL,
    effective_to    date,
    review_status   legal.review_status NOT NULL DEFAULT 'PENDING',
    CONSTRAINT approval_dates_ordered CHECK (effective_to IS NULL OR effective_to > effective_from)
);

CREATE TABLE legal.approval_conditions (
    approval_condition_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    approval_id  uuid NOT NULL REFERENCES legal.approvals(approval_id) ON DELETE CASCADE,
    expr_json    jsonb NOT NULL,
    expr_text    text NOT NULL,
    ordinal      integer NOT NULL DEFAULT 1,
    UNIQUE (approval_id, ordinal),
    CONSTRAINT approval_expr_is_object CHECK (jsonb_typeof(expr_json) = 'object')
);

-- ------------------------------------------------------------------ filings §13
CREATE TABLE legal.filings (
    filing_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    filing_code      text NOT NULL UNIQUE,
    filing_name      text NOT NULL,
    authority        legal.authority NOT NULL,
    form_name        text,                       -- 'PAS-3', 'MGT-14', 'SH-7'
    trigger_event    text NOT NULL REFERENCES legal.anchor_events(anchor_event),
    issue_type       legal.issue_type NOT NULL,
    company_type     legal.company_type NOT NULL DEFAULT 'ANY',
    listed_status    legal.listed_status NOT NULL DEFAULT 'UNKNOWN',
    exchange         legal.exchange NOT NULL DEFAULT 'ANY',
    stage            legal.compliance_stage NOT NULL,
    attachments      jsonb NOT NULL DEFAULT '[]'::jsonb,
    approval_dependency uuid REFERENCES legal.approvals(approval_id) ON DELETE SET NULL,
    rule_version_id  uuid REFERENCES legal.legal_rule_versions(rule_version_id) ON DELETE SET NULL,
    source_id        uuid NOT NULL REFERENCES legal.legal_sources(source_id) ON DELETE RESTRICT,
    provision_id     uuid REFERENCES legal.legal_provisions(provision_id) ON DELETE RESTRICT,
    source_reference text NOT NULL,
    source_page      integer,
    effective_from   date NOT NULL,
    effective_to     date,
    review_status    legal.review_status NOT NULL DEFAULT 'PENDING',
    CONSTRAINT filing_dates_ordered CHECK (effective_to IS NULL OR effective_to > effective_from)
);
COMMENT ON COLUMN legal.filings.trigger_event IS
  'The event that starts the clock. A filing without a trigger cannot be scheduled (brief §13).';

-- --------------------------------------------------------- filing_deadlines §15
-- "15 days after allotment" is stored as ALLOTMENT_DATE + 15 CALENDAR days,
-- never as a fixed date.
CREATE TABLE legal.filing_deadlines (
    deadline_id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    filing_id       uuid NOT NULL REFERENCES legal.filings(filing_id) ON DELETE CASCADE,
    anchor_event    text NOT NULL REFERENCES legal.anchor_events(anchor_event),
    direction       legal.deadline_direction NOT NULL DEFAULT 'AFTER',
    offset_value    integer NOT NULL CHECK (offset_value >= 0),
    offset_unit     text NOT NULL DEFAULT 'DAYS'
                    CHECK (offset_unit IN ('DAYS','MONTHS','YEARS')),
    day_type        legal.day_type NOT NULL DEFAULT 'CALENDAR',
    description     text NOT NULL,
    exception_note  text,
    source_id       uuid NOT NULL REFERENCES legal.legal_sources(source_id) ON DELETE RESTRICT,
    provision_id    uuid REFERENCES legal.legal_provisions(provision_id) ON DELETE RESTRICT,
    source_reference text NOT NULL,
    effective_from  date NOT NULL,
    effective_to    date,
    review_status   legal.review_status NOT NULL DEFAULT 'PENDING',
    CONSTRAINT deadline_dates_ordered CHECK (effective_to IS NULL OR effective_to > effective_from)
);

-- --------------------------------------------------- document_requirements §14
CREATE TABLE legal.document_requirements (
    doc_requirement_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    requirement_code   text NOT NULL,
    name               text NOT NULL,
    description        text,
    authority          legal.authority NOT NULL,
    exchange           legal.exchange NOT NULL DEFAULT 'ANY',
    issue_type         legal.issue_type NOT NULL,
    company_type       legal.company_type NOT NULL DEFAULT 'ANY',
    listed_status      legal.listed_status NOT NULL DEFAULT 'UNKNOWN',
    stage              legal.compliance_stage NOT NULL,
    necessity          legal.requirement_necessity NOT NULL DEFAULT 'MANDATORY',
    rule_version_id    uuid REFERENCES legal.legal_rule_versions(rule_version_id) ON DELETE SET NULL,
    filing_id          uuid REFERENCES legal.filings(filing_id) ON DELETE SET NULL,
    source_id          uuid NOT NULL REFERENCES legal.legal_sources(source_id) ON DELETE RESTRICT,
    provision_id       uuid REFERENCES legal.legal_provisions(provision_id) ON DELETE RESTRICT,
    source_table_id    uuid REFERENCES legal.document_tables(table_id) ON DELETE SET NULL,
    source_reference   text NOT NULL,
    source_page        integer,
    effective_from     date NOT NULL,
    effective_to       date,
    review_status      legal.review_status NOT NULL DEFAULT 'PENDING',
    UNIQUE (requirement_code, issue_type, stage, exchange),
    CONSTRAINT docreq_dates_ordered CHECK (effective_to IS NULL OR effective_to > effective_from)
);
COMMENT ON COLUMN legal.document_requirements.source_table_id IS
  'Exchange checklists express requirements as table rows; this links back to the exact grid.';

-- ------------------------------------------------------------- compliance_steps
CREATE TABLE legal.compliance_steps (
    step_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    issue_type   legal.issue_type NOT NULL,
    company_type legal.company_type NOT NULL DEFAULT 'ANY',
    listed_status legal.listed_status NOT NULL DEFAULT 'UNKNOWN',
    exchange     legal.exchange NOT NULL DEFAULT 'ANY',
    step_no      integer NOT NULL CHECK (step_no >= 1),
    stage        legal.compliance_stage NOT NULL,
    name         text NOT NULL,
    description  text,
    approval_id  uuid REFERENCES legal.approvals(approval_id) ON DELETE SET NULL,
    filing_id    uuid REFERENCES legal.filings(filing_id) ON DELETE SET NULL,
    rule_version_id uuid REFERENCES legal.legal_rule_versions(rule_version_id) ON DELETE SET NULL,
    source_id    uuid NOT NULL REFERENCES legal.legal_sources(source_id) ON DELETE RESTRICT,
    source_reference text NOT NULL,
    review_status legal.review_status NOT NULL DEFAULT 'PENDING',
    UNIQUE (issue_type, company_type, listed_status, exchange, step_no)
);

-- --------------------------------------------------------- compliance_timelines
CREATE TABLE legal.compliance_timelines (
    timeline_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    issue_type    legal.issue_type NOT NULL,
    event_name    text NOT NULL,
    anchor_event  text NOT NULL REFERENCES legal.anchor_events(anchor_event),
    direction     legal.deadline_direction NOT NULL DEFAULT 'AFTER',
    deadline_value integer NOT NULL CHECK (deadline_value >= 0),
    deadline_unit text NOT NULL DEFAULT 'DAYS' CHECK (deadline_unit IN ('DAYS','MONTHS','YEARS')),
    day_type      legal.day_type NOT NULL DEFAULT 'CALENDAR',
    authority     legal.authority NOT NULL,
    exchange      legal.exchange NOT NULL DEFAULT 'ANY',
    exception_note text,
    rule_version_id uuid REFERENCES legal.legal_rule_versions(rule_version_id) ON DELETE SET NULL,
    source_id     uuid NOT NULL REFERENCES legal.legal_sources(source_id) ON DELETE RESTRICT,
    provision_id  uuid REFERENCES legal.legal_provisions(provision_id) ON DELETE RESTRICT,
    source_reference text NOT NULL,
    effective_from date NOT NULL,
    effective_to  date,
    review_status legal.review_status NOT NULL DEFAULT 'PENDING',
    CONSTRAINT timeline_dates_ordered CHECK (effective_to IS NULL OR effective_to > effective_from)
);

COMMIT;

-- rollback:
--   DROP TABLE IF EXISTS legal.compliance_timelines, legal.compliance_steps,
--     legal.document_requirements, legal.filing_deadlines, legal.filings,
--     legal.approval_conditions, legal.approvals, legal.anchor_events CASCADE;
