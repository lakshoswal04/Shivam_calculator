-- 007 - Authentication, multi-tenancy, row-level security and platform tables
--
-- Tenancy model: an organisation (CA/CS/law firm) manages many client
-- companies. Isolation is enforced by PostgreSQL row-level security bound to
-- a per-request session variable, so an application bug cannot leak one
-- firm's client data to another.

BEGIN;

CREATE SCHEMA IF NOT EXISTS auth;
COMMENT ON SCHEMA auth IS 'Organisations, users, roles and sessions. The tenant boundary.';

CREATE TYPE auth.user_role AS ENUM
  ('COMPANY_USER','FINANCE_USER','LEGAL_REVIEWER','ADMINISTRATOR');

-- ============================================================ organisations
CREATE TABLE auth.organisations (
    org_id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name       text NOT NULL,
    slug       text NOT NULL UNIQUE,
    is_demo    boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT slug_shape CHECK (slug ~ '^[a-z0-9][a-z0-9-]{1,48}$')
);
COMMENT ON COLUMN auth.organisations.is_demo IS
  'Demo tenants are purgeable and their approvals are labelled in every payload.';

CREATE TABLE auth.users (
    user_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email         text NOT NULL,
    password_hash text NOT NULL,
    full_name     text NOT NULL,
    is_active     boolean NOT NULL DEFAULT true,
    last_login_at timestamptz,
    created_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT email_shape CHECK (email ~ '^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$')
);
-- Email is an identity, so it is unique case-insensitively.
CREATE UNIQUE INDEX users_email_lower_key ON auth.users (lower(email));

-- A user belongs to one or more organisations, with a role in each.
CREATE TABLE auth.memberships (
    membership_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id  uuid NOT NULL REFERENCES auth.organisations(org_id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES auth.users(user_id) ON DELETE CASCADE,
    role    auth.user_role NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (org_id, user_id)
);

-- Per-company grants within an organisation. Absence of a row means the user
-- sees every company in the org; a row restricts them to the listed ones.
CREATE TABLE auth.company_access (
    access_id  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id     uuid NOT NULL REFERENCES auth.organisations(org_id) ON DELETE CASCADE,
    user_id    uuid NOT NULL REFERENCES auth.users(user_id) ON DELETE CASCADE,
    company_id uuid NOT NULL,
    granted_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, company_id)
);

CREATE TABLE auth.refresh_tokens (
    token_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    uuid NOT NULL REFERENCES auth.users(user_id) ON DELETE CASCADE,
    org_id     uuid NOT NULL REFERENCES auth.organisations(org_id) ON DELETE CASCADE,
    token_hash char(64) NOT NULL UNIQUE,   -- SHA-256; the raw token is never stored
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON auth.refresh_tokens (user_id) WHERE revoked_at IS NULL;

-- ==================================================== tenant key on company data
ALTER TABLE company.companies                ADD COLUMN org_id uuid;
ALTER TABLE company.company_classifications  ADD COLUMN org_id uuid;
ALTER TABLE company.capital_snapshots        ADD COLUMN org_id uuid;
ALTER TABLE company.share_classes            ADD COLUMN org_id uuid;
ALTER TABLE company.shareholders             ADD COLUMN org_id uuid;
ALTER TABLE company.holdings                 ADD COLUMN org_id uuid;
ALTER TABLE company.securities               ADD COLUMN org_id uuid;
ALTER TABLE company.security_terms           ADD COLUMN org_id uuid;
ALTER TABLE company.security_conversions     ADD COLUMN org_id uuid;
ALTER TABLE company.issues                   ADD COLUMN org_id uuid;
ALTER TABLE company.issue_allottees          ADD COLUMN org_id uuid;
ALTER TABLE assess.scenarios                 ADD COLUMN org_id uuid;
ALTER TABLE assess.scenario_inputs           ADD COLUMN org_id uuid;
ALTER TABLE assess.assessment_results        ADD COLUMN org_id uuid;
ALTER TABLE assess.assessment_rule_results   ADD COLUMN org_id uuid;
ALTER TABLE assess.assessment_calculations   ADD COLUMN org_id uuid;

DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'company.companies','company.company_classifications','company.capital_snapshots',
    'company.share_classes','company.shareholders','company.holdings',
    'company.securities','company.security_terms','company.security_conversions',
    'company.issues','company.issue_allottees',
    'assess.scenarios','assess.scenario_inputs','assess.assessment_results',
    'assess.assessment_rule_results','assess.assessment_calculations']
  LOOP
    EXECUTE format('ALTER TABLE %s ALTER COLUMN org_id SET NOT NULL', t);
    EXECUTE format('ALTER TABLE %s ADD CONSTRAINT %s_org_fk FOREIGN KEY (org_id) '
                   'REFERENCES auth.organisations(org_id) ON DELETE CASCADE',
                   t, replace(split_part(t,'.',2),'.','_'));
    EXECUTE format('CREATE INDEX ON %s (org_id)', t);
  END LOOP;
END $$;

-- ======================================================= row-level security
-- Every request sets app.current_org; policies compare against it. The
-- setting is read with the missing_ok flag so a session that has not set it
-- simply sees nothing, rather than erroring.
CREATE FUNCTION auth.current_org() RETURNS uuid
LANGUAGE sql STABLE AS $$
  SELECT nullif(current_setting('app.current_org', true), '')::uuid;
$$;
COMMENT ON FUNCTION auth.current_org() IS
  'Tenant in scope for this transaction. NULL means no rows are visible.';

DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'company.companies','company.company_classifications','company.capital_snapshots',
    'company.share_classes','company.shareholders','company.holdings',
    'company.securities','company.security_terms','company.security_conversions',
    'company.issues','company.issue_allottees',
    'assess.scenarios','assess.scenario_inputs','assess.assessment_results',
    'assess.assessment_rule_results','assess.assessment_calculations']
  LOOP
    EXECUTE format('ALTER TABLE %s ENABLE ROW LEVEL SECURITY', t);
    -- FORCE makes the policy apply to the table owner too; without it the
    -- owner silently bypasses RLS and the isolation test passes for the
    -- wrong reason.
    EXECUTE format('ALTER TABLE %s FORCE ROW LEVEL SECURITY', t);
    EXECUTE format(
      'CREATE POLICY tenant_isolation ON %s USING (org_id = auth.current_org()) '
      'WITH CHECK (org_id = auth.current_org())', t);
  END LOOP;
END $$;

-- ============================================================ what-if lineage
ALTER TABLE assess.scenarios
  ADD COLUMN parent_scenario_id uuid REFERENCES assess.scenarios(scenario_id) ON DELETE SET NULL,
  ADD COLUMN variant_label text,
  ADD CONSTRAINT scenario_not_own_parent CHECK (parent_scenario_id IS DISTINCT FROM scenario_id);

-- ============================================================== notifications
CREATE TABLE auth.notifications (
    notification_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id  uuid NOT NULL REFERENCES auth.organisations(org_id) ON DELETE CASCADE,
    user_id uuid REFERENCES auth.users(user_id) ON DELETE CASCADE,
    kind    text NOT NULL,
    title   text NOT NULL,
    body    text,
    link    text,
    read_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON auth.notifications (org_id, user_id) WHERE read_at IS NULL;

-- =================================================================== reports
CREATE TABLE assess.reports (
    report_id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id        uuid NOT NULL REFERENCES auth.organisations(org_id) ON DELETE CASCADE,
    assessment_id uuid NOT NULL REFERENCES assess.assessment_results(assessment_id) ON DELETE CASCADE,
    format        text NOT NULL CHECK (format IN ('PDF','JSON','HTML')),
    storage_key   text,
    payload       jsonb,
    generated_at  timestamptz NOT NULL DEFAULT now(),
    generated_by  uuid REFERENCES auth.users(user_id) ON DELETE SET NULL
);
ALTER TABLE assess.reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE assess.reports FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON assess.reports
  USING (org_id = auth.current_org()) WITH CHECK (org_id = auth.current_org());

-- ============================================== review queue and source gaps
-- Replaces data/reports/review_queue.json with queryable tables.
CREATE TABLE legal.source_gaps (
    gap_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code        text NOT NULL UNIQUE,
    severity    text NOT NULL CHECK (severity IN ('BLOCKER','GAP','INFO')),
    title       text NOT NULL,
    detail      text NOT NULL,
    action_required text NOT NULL,
    blocks_issue_types legal.issue_type[] NOT NULL DEFAULT '{}',
    provisions_required text[] NOT NULL DEFAULT '{}',
    resolved_at timestamptz,
    resolved_by text,
    created_at  timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE legal.source_gaps IS
  'Sources V1 needs but does not have. Surfaced in every affected assessment.';

CREATE TABLE legal.review_queue (
    item_id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    item_type   text NOT NULL CHECK (item_type IN
                  ('RULE_VERSION','SOURCE_GAP','CONFLICT','CLASSIFICATION','EXTRACTION')),
    rule_version_id uuid REFERENCES legal.legal_rule_versions(rule_version_id) ON DELETE CASCADE,
    gap_id      uuid REFERENCES legal.source_gaps(gap_id) ON DELETE CASCADE,
    conflict_id uuid REFERENCES legal.legal_conflicts(conflict_id) ON DELETE CASCADE,
    source_id   uuid REFERENCES legal.legal_sources(source_id) ON DELETE CASCADE,
    title       text NOT NULL,
    detail      text,
    status      legal.review_status NOT NULL DEFAULT 'PENDING',
    assigned_to uuid REFERENCES auth.users(user_id) ON DELETE SET NULL,
    resolved_at timestamptz,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON legal.review_queue (status, item_type);

-- ==================================== provision text: heading + body are one
-- The parser stores a provision's opening line in `heading` and the remainder
-- in `body_text`. Neither column alone is the provision, so every read path
-- must join them. display_text additionally drops the trailing gazette
-- footnote apparatus ("299 Substituted by ...") for reading; body_text stays
-- verbatim as evidence.
CREATE FUNCTION legal.provision_full_text(p_heading text, p_body text)
RETURNS text LANGUAGE sql IMMUTABLE AS $$
  SELECT btrim(coalesce(p_heading,'') || ' ' || coalesce(p_body,''));
$$;

CREATE FUNCTION legal.provision_display_text(p_heading text, p_body text)
RETURNS text LANGUAGE sql IMMUTABLE AS $$
  SELECT btrim(regexp_replace(
           legal.provision_full_text(p_heading, p_body),
           '\s+\d{1,3}\s+(Substituted|Inserted|Omitted|Added|Renumbered)\s+by\s+the.*$',
           '', 'i'));
$$;

CREATE VIEW legal.v_provisions_readable AS
SELECT p.provision_id, p.document_id, p.instrument_id, p.parent_id,
       p.provision_type, p.number, p.citation, p.citation_uid, p.citation_ambiguous,
       p.depth, p.page_from, p.page_to, p.amended, p.amendment_markers,
       p.heading, p.body_text,
       legal.provision_full_text(p.heading, p.body_text)    AS full_text,
       legal.provision_display_text(p.heading, p.body_text) AS display_text,
       i.label AS instrument_label,
       s.file_name, s.file_hash, s.authority, s.source_priority
FROM legal.legal_provisions p
JOIN legal.legal_instruments i USING (instrument_id)
JOIN legal.legal_documents  d USING (document_id)
JOIN legal.legal_sources    s ON s.source_id = d.source_id;
COMMENT ON VIEW legal.v_provisions_readable IS
  'Provisions with heading and body joined. Use this for display and rule authoring.';

COMMIT;

-- rollback:
--   DROP VIEW IF EXISTS legal.v_provisions_readable;
--   DROP FUNCTION IF EXISTS legal.provision_display_text, legal.provision_full_text;
--   DROP TABLE IF EXISTS legal.review_queue, legal.source_gaps, assess.reports,
--     auth.notifications, auth.refresh_tokens, auth.company_access,
--     auth.memberships, auth.users, auth.organisations CASCADE;
--   DROP FUNCTION IF EXISTS auth.current_org(); DROP TYPE IF EXISTS auth.user_role;
--   DROP SCHEMA IF EXISTS auth CASCADE;
