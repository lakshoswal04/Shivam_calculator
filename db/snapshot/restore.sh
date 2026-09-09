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

echo "→ restoring snapshot into the target database"
gunzip -c legal_rules.sql.gz | psql -v ON_ERROR_STOP=1 -d "$DB_URL" >/dev/null

echo "→ verifying"
psql -tA -d "$DB_URL" <<'SQL'
SELECT '  provisions      = ' || count(*) FROM legal.legal_provisions
UNION ALL SELECT '  rules live      = ' || count(*) FROM legal.v_active_rule_versions
UNION ALL SELECT '  calculations    = ' || count(*) FROM calc.v_active_calculation_versions
UNION ALL SELECT '  companies       = ' || count(*) FROM company.companies
UNION ALL SELECT '  quality failures= ' || count(*) FROM legal.v_quality_checks WHERE failing_rows > 0;
SQL

echo "→ confirming row-level security is enforced for this role"
psql -tA -d "$DB_URL" <<'SQL'
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles
             WHERE rolname = current_user AND (rolsuper OR rolbypassrls)) THEN
    RAISE WARNING 'Role % bypasses RLS -- tenant isolation will NOT hold.', current_user;
  ELSE
    RAISE NOTICE 'role % is subject to row-level security', current_user;
  END IF;
END $$;
SQL

cat <<'NOTE'

  The snapshot includes a DEMO organisation whose four accounts share the
  password "demo1234". Anyone who can reach the deployment can sign in with
  them. Before exposing this publicly, run:

      backend/.venv/bin/python db/seed/demo/seed_demo.py --purge --dsn "<DATABASE_URL>"

NOTE
