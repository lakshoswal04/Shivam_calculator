-- Row-level security must isolate tenants at the DATABASE, not just the API.
-- Every check below must print PASS.
\set ON_ERROR_STOP 1
\pset pager off
BEGIN;

INSERT INTO auth.organisations (org_id, name, slug) VALUES
 ('11111111-1111-1111-1111-111111111111','Firm A','firm-a'),
 ('22222222-2222-2222-2222-222222222222','Firm B','firm-b');

-- Seed one company per firm while RLS is satisfied for each in turn.
SET LOCAL app.current_org = '11111111-1111-1111-1111-111111111111';
INSERT INTO company.companies (org_id, name, cin)
VALUES ('11111111-1111-1111-1111-111111111111','Alpha Industries Ltd', NULL);

SET LOCAL app.current_org = '22222222-2222-2222-2222-222222222222';
INSERT INTO company.companies (org_id, name, cin)
VALUES ('22222222-2222-2222-2222-222222222222','Beta Traders Ltd', NULL);

\echo ''
\echo '--- tenant isolation ---'
SET LOCAL app.current_org = '11111111-1111-1111-1111-111111111111';
SELECT CASE WHEN count(*) = 1 AND min(name) = 'Alpha Industries Ltd'
            THEN 'PASS' ELSE 'FAIL' END AS result,
       'Firm A sees only its own company' AS check, count(*) AS rows
FROM company.companies;

SET LOCAL app.current_org = '22222222-2222-2222-2222-222222222222';
SELECT CASE WHEN count(*) = 1 AND min(name) = 'Beta Traders Ltd'
            THEN 'PASS' ELSE 'FAIL' END AS result,
       'Firm B sees only its own company' AS check, count(*) AS rows
FROM company.companies;

\echo ''
\echo '--- direct id lookup across tenants leaks nothing ---'
SET LOCAL app.current_org = '22222222-2222-2222-2222-222222222222';
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END AS result,
       'Firm B cannot read Firm A rows even by direct query' AS check
FROM company.companies WHERE name = 'Alpha Industries Ltd';

\echo ''
\echo '--- no tenant set means no rows (fail closed) ---'
SET LOCAL app.current_org = '';
SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END AS result,
       'Unset tenant sees nothing rather than everything' AS check
FROM company.companies;

\echo ''
\echo '--- cannot write into another tenant ---'
SET LOCAL app.current_org = '11111111-1111-1111-1111-111111111111';
DO $$
BEGIN
  INSERT INTO company.companies (org_id, name)
  VALUES ('22222222-2222-2222-2222-222222222222','Smuggled Ltd');
  RAISE WARNING 'FAIL  cross-tenant INSERT was allowed';
EXCEPTION WHEN insufficient_privilege OR check_violation THEN
  RAISE NOTICE 'PASS  cross-tenant INSERT rejected by WITH CHECK';
END $$;

\echo ''
\echo '--- owner does not bypass RLS (FORCE is on) ---'
SELECT CASE WHEN relrowsecurity AND relforcerowsecurity THEN 'PASS' ELSE 'FAIL' END AS result,
       'company.companies has RLS enabled AND forced' AS check
FROM pg_class WHERE oid = 'company.companies'::regclass;

SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END AS result,
       'every tenant table has RLS forced' AS check, count(*) AS unforced
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname IN ('company','assess') AND c.relkind = 'r'
  AND NOT (c.relrowsecurity AND c.relforcerowsecurity);

ROLLBACK;
