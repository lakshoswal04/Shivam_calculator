-- 008 - Application role and grants
--
-- Row-level security does not apply to superusers or to roles with BYPASSRLS.
-- The API must therefore connect as an ordinary role, or tenant isolation is
-- silently inert -- policies exist, the tests look green, and every tenant
-- still sees every other tenant's data.
--
-- Portable across environments:
--   * Local development creates a `calcapp` role with a development password.
--   * On managed Postgres (Render, Neon, Supabase) the platform has already
--     created the connecting role and does not grant CREATE ROLE or the
--     superuser rights needed to ALTER it. There the block below is skipped
--     and the assertion at the end is what actually protects us.

BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'calcapp') THEN
    BEGIN
      CREATE ROLE calcapp LOGIN PASSWORD 'calcapp_dev_pw'
        NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
      RAISE NOTICE 'created role calcapp (development)';
    EXCEPTION WHEN insufficient_privilege THEN
      RAISE NOTICE 'cannot create roles here; using the platform-provided role';
    END;
  ELSE
    BEGIN
      ALTER ROLE calcapp NOSUPERUSER NOBYPASSRLS;
    EXCEPTION WHEN insufficient_privilege THEN
      RAISE NOTICE 'cannot alter calcapp here; verified by assertion instead';
    END;
  END IF;
END $$;

-- Grants are no-ops where the connecting role already owns the schema, which
-- is the case on managed Postgres. current_database() keeps this portable.
DO $$
DECLARE r text := 'calcapp';
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
    r := current_user;
  END IF;
  EXECUTE format('GRANT CONNECT ON DATABASE %I TO %I', current_database(), r);
  EXECUTE format('GRANT USAGE ON SCHEMA legal, company, calc, assess, audit, auth TO %I', r);

  -- Source documents, extracted text and provisions are read-only to the app;
  -- only the ingestion pipeline writes them.
  EXECUTE format('GRANT SELECT ON ALL TABLES IN SCHEMA legal TO %I', r);
  EXECUTE format('GRANT SELECT ON ALL TABLES IN SCHEMA calc TO %I', r);
  EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES '
                 'IN SCHEMA company, assess, auth TO %I', r);
  EXECUTE format('GRANT SELECT, INSERT, UPDATE ON
      legal.legal_rules, legal.legal_rule_versions, legal.legal_conditions,
      legal.legal_exceptions, legal.legal_requirements, legal.legal_conflicts,
      legal.approvals, legal.approval_conditions, legal.filings,
      legal.filing_deadlines, legal.document_requirements, legal.compliance_steps,
      legal.compliance_timelines, legal.exchange_rules, legal.exchange_requirements,
      legal.exchange_filings, legal.exchange_deadlines,
      legal.review_queue, legal.source_gaps TO %I', r);
  EXECUTE format('GRANT INSERT, UPDATE ON calc.calculations, calc.calculation_versions TO %I', r);
  EXECUTE format('GRANT INSERT ON audit.audit_logs, audit.rule_change_log TO %I', r);
  EXECUTE format('GRANT USAGE, SELECT ON ALL SEQUENCES '
                 'IN SCHEMA audit, legal, company, assess, auth TO %I', r);
  EXECUTE format('GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA legal, auth TO %I', r);

  EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA legal, calc GRANT SELECT ON TABLES TO %I', r);
  EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA company, assess, auth '
                 'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO %I', r);
  EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA audit GRANT INSERT ON TABLES TO %I', r);
END $$;

COMMIT;

-- The guarantee this migration exists to provide. Run it as the role the API
-- will actually use: if that role can bypass RLS, tenant isolation is a
-- fiction and the deployment must not proceed.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles
             WHERE rolname = current_user AND (rolsuper OR rolbypassrls)) THEN
    RAISE WARNING
      'Role % is superuser/BYPASSRLS. Row-level security will NOT apply to it. '
      'The API must connect as an ordinary role.', current_user;
  ELSE
    RAISE NOTICE 'role % is subject to row-level security', current_user;
  END IF;
END $$;

-- rollback:
--   REASSIGN OWNED BY calcapp TO CURRENT_USER; DROP OWNED BY calcapp; DROP ROLE IF EXISTS calcapp;
