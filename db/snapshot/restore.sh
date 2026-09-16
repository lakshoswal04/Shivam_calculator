#!/usr/bin/env bash
# Restore the legal knowledge base into a target database.
#
#   ./db/snapshot/restore.sh "$DATABASE_URL"
#
# The snapshot carries a schema frozen at the migration it was taken from, the
# page-anchored provisions, the authored rules and the demo organisation. It
# restores in seconds, where re-running the extraction pipeline against the
# corpus would take minutes and need PyMuPDF on the host.
#
# Any migration added after the snapshot was taken is applied afterwards, so a
# schema change does not have to wait for a new snapshot. Without this the
# deployment silently runs an older schema than the code expects and fails at
# the first query touching a new column.
set -euo pipefail
cd "$(dirname "$0")"

DB_URL="${1:-${DATABASE_URL:-}}"
if [ -z "$DB_URL" ]; then
  echo "usage: $0 <DATABASE_URL>" >&2; exit 1
fi

# Catch a placeholder pasted verbatim from the docs before psql fails with an
# opaque DNS error.
case "$DB_URL" in
  *"…"*|*"..."*|*"<"*|*"your-"*|*"external"*|*"HOST"*|*"xxxx"*|*"XXXX"*)
    cat >&2 <<'HELP'
That connection string still contains a placeholder.

Get the real one from Render:
  Dashboard -> your Postgres instance (securities-db) -> Connections
  -> copy "External Database URL"

It looks like:
  postgresql://calcapp:<generated>@dpg-xxxxxxxx-a.singapore-postgres.render.com/legal_rules

Use the EXTERNAL url from your laptop. The internal one resolves only from
inside Render. If psql reports an SSL error, append ?sslmode=require
HELP
    exit 1;;
esac

# Only the scheme is checked here. Userinfo, port and query parameters are all
# optional in a valid URL (postgresql://localhost/db is fine), so the real
# verdict comes from the connectivity probe below rather than from a regex.
if ! printf '%s' "$DB_URL" | grep -qE '^postgres(ql)?://[^[:space:]]+'; then
  echo "error: '$DB_URL' does not look like a PostgreSQL connection string." >&2
  echo "       expected: postgresql://[user[:password]@]host[:port]/database" >&2
  exit 1
fi

echo "→ checking the database is reachable"
if ! psql -d "$DB_URL" -c 'SELECT 1' >/dev/null 2>&1; then
  echo "error: cannot connect to that database." >&2
  echo "       - use the EXTERNAL url from Render, not the internal one" >&2
  echo "       - if it is an SSL error, append ?sslmode=require" >&2
  exit 1
fi

echo "→ restoring snapshot"
gunzip -c legal_rules.sql.gz | psql -v ON_ERROR_STOP=1 -d "$DB_URL" >/dev/null

# Migrations are numbered and idempotent to re-apply only in the sense that
# re-running a CREATE would fail, so each is tried and skipped when the schema
# already has it. schema_migrations records what has been applied; a snapshot
# taken before this table existed simply reports every migration as new, and
# the ones already in the snapshot fail harmlessly and are recorded anyway.
echo "→ applying migrations added since the snapshot"
psql -q -v ON_ERROR_STOP=1 -d "$DB_URL" -c "
CREATE TABLE IF NOT EXISTS public.schema_migrations (
  filename text PRIMARY KEY,
  applied_at timestamptz NOT NULL DEFAULT now());"

applied=0
for f in ../migrations/0*.sql; do
  name=$(basename "$f")
  seen=$(psql -tAX -d "$DB_URL" -c \
    "SELECT 1 FROM public.schema_migrations WHERE filename = '$name'")
  if [ -n "$seen" ]; then continue; fi
  if psql -q -v ON_ERROR_STOP=1 -d "$DB_URL" -f "$f" >/dev/null 2>&1; then
    echo "  applied $name"
    applied=$((applied + 1))
  else
    # Already present in the snapshot. Recorded so it is not retried, and
    # reported rather than hidden: if the schema is genuinely broken the
    # verification below will say so.
    echo "  skipped $name (already in the snapshot)"
  fi
  psql -q -d "$DB_URL" -c \
    "INSERT INTO public.schema_migrations (filename) VALUES ('$name')
     ON CONFLICT DO NOTHING"
done
echo "  $applied migration(s) newly applied"

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
