-- 002 - Source and document layer (brief §2, §3, §5)
-- Answers, for any rule: "which exact document, page and clause did this come from?"

BEGIN;

-- ---------------------------------------------------------------- legal_sources
-- One row per physical document. The SHA-256 is the document's identity: the
-- same bytes are the same source, whatever the file is called.
CREATE TABLE legal.legal_sources (
    source_id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_key         text        NOT NULL UNIQUE,   -- stable slug from the pipeline
    authority            legal.authority NOT NULL,
    document_type        legal.document_type NOT NULL,
    title                text        NOT NULL,
    file_name            text        NOT NULL,
    local_file_path      text        NOT NULL,
    file_type            text        NOT NULL,
    file_size_bytes      bigint      NOT NULL CHECK (file_size_bytes > 0),
    file_hash            char(64)    NOT NULL UNIQUE,   -- SHA-256, lowercase hex
    official_url         text,
    publication_date     date,
    amendment_date       date,
    effective_date       date,
    version              text,
    status               text        NOT NULL DEFAULT 'ACTIVE',
    retrieved_date       timestamptz,
    source_priority      legal.source_priority NOT NULL,
    consolidation_status legal.consolidation_status NOT NULL DEFAULT 'UNKNOWN',
    as_amended_upto      date,
    scope                legal.doc_scope NOT NULL DEFAULT 'COMPANY',
    page_count           integer CHECK (page_count IS NULL OR page_count > 0),
    in_container         text,
    notes                text,
    human_review_required boolean NOT NULL DEFAULT true,
    review_reasons       jsonb   NOT NULL DEFAULT '[]'::jsonb,
    created_at           timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT file_hash_is_hex CHECK (file_hash ~ '^[0-9a-f]{64}$'),
    -- A document claiming to be consolidated must say up to when, or the claim
    -- cannot be checked against a transaction date.
    CONSTRAINT consolidated_needs_date
        CHECK (consolidation_status <> 'CONSOLIDATED' OR as_amended_upto IS NOT NULL),
    CONSTRAINT amendment_not_before_publication
        CHECK (amendment_date IS NULL OR publication_date IS NULL
               OR amendment_date >= publication_date)
);
COMMENT ON TABLE  legal.legal_sources IS 'Immutable record of each source document. Originals are never modified.';
COMMENT ON COLUMN legal.legal_sources.file_hash IS 'SHA-256 of the original bytes; the document''s identity.';
COMMENT ON COLUMN legal.legal_sources.consolidation_status IS
  'AS_ENACTED/REFERENCE_ONLY text does not carry later amendments and must not source a production rule.';

CREATE INDEX ON legal.legal_sources (authority, document_type);
CREATE INDEX ON legal.legal_sources (source_priority);
CREATE INDEX ON legal.legal_sources (scope);

-- ------------------------------------------------------------- legal_documents
-- One row per extraction run over a source, so re-extraction with a better
-- tool is a new row rather than a destructive overwrite.
CREATE TABLE legal.legal_documents (
    document_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id         uuid NOT NULL REFERENCES legal.legal_sources(source_id) ON DELETE RESTRICT,
    extraction_tool   text NOT NULL,
    extraction_run_at timestamptz NOT NULL DEFAULT now(),
    page_count        integer NOT NULL CHECK (page_count >= 0),
    block_count       integer NOT NULL DEFAULT 0,
    table_count       integer NOT NULL DEFAULT 0,
    char_count        bigint  NOT NULL DEFAULT 0,
    ocr_used          boolean NOT NULL DEFAULT false,
    ocr_confidence    numeric(5,2) CHECK (ocr_confidence IS NULL
                                          OR ocr_confidence BETWEEN 0 AND 100),
    is_current        boolean NOT NULL DEFAULT true,
    notes             text,
    -- OCR text is never assumed accurate (brief §3).
    CONSTRAINT ocr_requires_confidence
        CHECK (NOT ocr_used OR ocr_confidence IS NOT NULL)
);
CREATE UNIQUE INDEX one_current_extraction_per_source
    ON legal.legal_documents (source_id) WHERE is_current;

-- --------------------------------------------------------------- document_pages
-- Raw and cleaned text are both retained; cleaning never overwrites raw (brief §4).
CREATE TABLE legal.document_pages (
    page_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id  uuid NOT NULL REFERENCES legal.legal_documents(document_id) ON DELETE CASCADE,
    page_no      integer NOT NULL CHECK (page_no >= 1),
    raw_text     text NOT NULL,
    cleaned_text text NOT NULL,
    char_count_raw   integer NOT NULL,
    char_count_clean integer NOT NULL,
    n_images     integer NOT NULL DEFAULT 0,
    ocr_used     boolean NOT NULL DEFAULT false,
    low_text     boolean NOT NULL DEFAULT false,
    human_review_required boolean NOT NULL DEFAULT false,
    UNIQUE (document_id, page_no)
);
COMMENT ON COLUMN legal.document_pages.raw_text IS 'Verbatim extractor output. Never edited, never AI-generated.';

-- ------------------------------------------------------------------ text_blocks
CREATE TABLE legal.text_blocks (
    block_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id uuid NOT NULL REFERENCES legal.legal_documents(document_id) ON DELETE CASCADE,
    page_no     integer NOT NULL CHECK (page_no >= 1),
    block_index integer NOT NULL,
    block_type  text NOT NULL,
    bbox        numeric[] ,
    font_size   numeric(6,2),
    bold        boolean,
    text        text NOT NULL,
    UNIQUE (document_id, page_no, block_index)
);
CREATE INDEX ON legal.text_blocks (document_id, block_type);

-- ----------------------------------------------------------------- doc_tables
CREATE TABLE legal.document_tables (
    table_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id uuid NOT NULL REFERENCES legal.legal_documents(document_id) ON DELETE CASCADE,
    page_no     integer NOT NULL,
    table_index integer NOT NULL,
    sheet_name  text,
    grid        jsonb NOT NULL,
    UNIQUE (document_id, page_no, table_index)
);
COMMENT ON TABLE legal.document_tables IS
  'Exchange checklists carry their requirements in tables; the grid is preserved verbatim.';

-- ------------------------------------------------------------ legal_instruments
CREATE TABLE legal.legal_instruments (
    instrument_id  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id      uuid NOT NULL REFERENCES legal.legal_sources(source_id) ON DELETE RESTRICT,
    label          text NOT NULL,          -- 'SEBI (ICDR) Regulations, 2018'
    short_code     text,                   -- 'ICDR'
    instrument_kind legal.instrument_kind NOT NULL,
    authority      legal.authority NOT NULL,
    year           integer CHECK (year IS NULL OR year BETWEEN 1850 AND 2100),
    UNIQUE (source_id, label)
);

-- ------------------------------------------------------------ legal_provisions
-- One recursive table covers Act/Rules/Regulations alike. Indian citations nest
-- to arbitrary depth - s.62(1)(a)(ii) plus provisos - which fixed section/
-- clause tables cannot express. Compatibility views in 006 preserve the
-- legal_sections / legal_regulations / legal_clauses query surface.
CREATE TABLE legal.legal_provisions (
    provision_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id    uuid NOT NULL REFERENCES legal.legal_documents(document_id) ON DELETE CASCADE,
    instrument_id  uuid NOT NULL REFERENCES legal.legal_instruments(instrument_id) ON DELETE CASCADE,
    parent_id      uuid REFERENCES legal.legal_provisions(provision_id) ON DELETE CASCADE,
    seq            integer NOT NULL,
    provision_type legal.provision_type NOT NULL,
    number         text NOT NULL DEFAULT '',
    heading        text NOT NULL DEFAULT '',
    citation       text NOT NULL,
    citation_uid   text NOT NULL,
    citation_path  text NOT NULL DEFAULT '',
    citation_ambiguous boolean NOT NULL DEFAULT false,
    depth          integer NOT NULL CHECK (depth >= 0),
    page_from      integer NOT NULL CHECK (page_from >= 1),
    page_to        integer NOT NULL CHECK (page_to >= 1),
    char_start     integer NOT NULL DEFAULT 0,
    body_text      text NOT NULL DEFAULT '',
    body_chars     integer NOT NULL DEFAULT 0,
    text_hash      char(64),
    -- Footnote markers showing the text was substituted by a later amendment.
    amendment_markers jsonb NOT NULL DEFAULT '[]'::jsonb,
    amended        boolean NOT NULL DEFAULT false,
    inline_split   boolean NOT NULL DEFAULT false,
    references_found jsonb NOT NULL DEFAULT '[]'::jsonb,
    UNIQUE (document_id, seq),
    UNIQUE (citation_uid),
    CONSTRAINT page_range_sane CHECK (page_to >= page_from),
    CONSTRAINT no_self_parent   CHECK (parent_id IS NULL OR parent_id <> provision_id)
);
COMMENT ON TABLE legal.legal_provisions IS
  'Recursive provision tree. citation is the human-readable legal citation and may repeat (Schedules restart numbering); citation_uid is the unique key.';
COMMENT ON COLUMN legal.legal_provisions.amendment_markers IS
  'Gazette footnote markers (e.g. 305[90 trading days]) indicating amended text; drives version review.';

CREATE INDEX ON legal.legal_provisions (instrument_id, provision_type, number);
CREATE INDEX ON legal.legal_provisions (parent_id);
CREATE INDEX ON legal.legal_provisions (document_id, page_from);
CREATE INDEX provisions_citation_trgm ON legal.legal_provisions (citation text_pattern_ops);
CREATE INDEX ON legal.legal_provisions (amended) WHERE amended;

COMMIT;

-- rollback:
--   DROP TABLE IF EXISTS legal.legal_provisions, legal.legal_instruments,
--     legal.document_tables, legal.text_blocks, legal.document_pages,
--     legal.legal_documents, legal.legal_sources CASCADE;
