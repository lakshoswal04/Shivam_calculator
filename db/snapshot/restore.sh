#!/usr/bin/env bash
# Restore the legal knowledge base into a target database.
#
#   ./db/snapshot/restore.sh "$DATABASE_URL"
#
# The snapshot carries the full schema (migrations 001-011), the 7,369
# page-anchored provisions, the authored rules and the demo organisation. It
# restores in seconds, where re-running the extraction pipeline against 1,176
# pages of PDF would take minutes and need PyMuPDF on the host.
set -euo pipefail
cd "$(dirname "$0")"

DB_URL="${1:-${DATABASE_URL:-}}"
if [ -z "$DB_URL" ]; then
  echo "usage: $0 <DATABASE_URL>" >&2; exit 1
fi

echo "→ restoring snapshot"
gunzip -c legal_rules.sql.gz | psql -v ON_ERROR_STOP=1 -d "$DB_URL" >/dev/null

echo "→ verifying the legal knowledge base"
psql -tA -d "$DB_URL" <<'SQL'
SELECT '  provisions       = ' || count(*) FROM legal.legal_provisions
UNION ALL SELECT '  rules live       = ' || count(*) FROM legal.v_active_rule_versions
UNION ALL SELECT '  calculations     = ' || count(*) FROM calc.v_active_calculation_versions
UNION ALL SELECT '  source gaps open = ' || count(*) FROM legal.source_gaps WHERE resolved_at IS NULL
UNION ALL SELECT '  quality failures = ' || count(*) FROM legal.v_quality_checks WHERE failing_rows > 0;
SQL

# Company data is tenant-scoped, so it is only countable inside a tenant. A
# zero here without setting app.current_org is row-level security working, not
# missing data -- the count below sets a tenant so the number is meaningful.
echo "→ verifying tenant data (inside the demo tenant)"
psql -tA -d "$DB_URL" <<'SQL'
\o /dev/null
SELECT set_config('app.current_org',
       (SELECT org_id::text FROM auth.organisations ORDER BY created_at LIMIT 1), false);
\o
SELECT '  companies        = ' || count(*) FROM company.companies;
SELECT '  users            = ' || count(*) FROM auth.users;
SQL

echo "→ checking row-level security applies to this role"
psql -tA -d "$DB_URL" -c "
SELECT CASE WHEN rolsuper OR rolbypassrls
  THEN '  WARNING: role ' || rolname || ' bypasses RLS - tenant isolation will NOT hold'
  ELSE '  ok: role ' || rolname || ' is subject to row-level security'
  END FROM pg_roles WHERE rolname = current_user;"

cat <<'NOTE'

  The snapshot includes a DEMO organisation whose four accounts share the
  password "demo1234". Anyone who can reach the deployment can sign in with
  them. Before exposing this publicly, run:

      backend/.venv/bin/python db/seed/demo/seed_demo.py --purge --dsn "<DATABASE_URL>"

NOTE
