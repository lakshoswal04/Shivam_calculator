#!/usr/bin/env bash
# Regenerate the deployment snapshot from a local database.
#
#   ./db/snapshot/create.sh [source-database]     # default: legal_rules_dev
#
# The snapshot is how a deployment gets the corpus without running the
# extraction pipeline, which needs PyMuPDF and minutes of CPU against the
# PDFs. It must be regenerated whenever the corpus, the authored rules or the
# schema change, or the deployed site will keep serving the previous corpus
# while the code expects the current one.
#
# --no-owner and --no-acl keep it restorable as whatever role the target
# happens to use; roles and grants are established by migration 008.
set -euo pipefail
cd "$(dirname "$0")"

DB="${1:-legal_rules_dev}"
OUT="legal_rules.sql.gz"

if ! psql -d "$DB" -c 'SELECT 1' >/dev/null 2>&1; then
  echo "error: cannot reach database '$DB'." >&2
  exit 1
fi

echo "→ summarising $DB"
psql -tA -d "$DB" <<'SQL'
SELECT '  provisions   = ' || count(*) FROM legal.legal_provisions
UNION ALL SELECT '  sources      = ' || count(*) FROM legal.legal_sources
UNION ALL SELECT '  rules live   = ' || count(*) FROM legal.v_active_rule_versions
UNION ALL SELECT '  quality fail = ' || count(*) FROM legal.v_quality_checks WHERE failing_rows > 0;
SQL

# Company rows are tenant-scoped, so this only reads as more than zero for a
# role that bypasses RLS - which is the normal case for a local dev superuser.
# It is reported because the backend test suite creates companies and never
# removes them: snapshotting straight after a test run would ship dozens of
# "Test Co ..." records to every deployment. Re-seed before snapshotting:
#   backend/.venv/bin/python db/seed/demo/seed_demo.py --purge --dsn "dbname=$DB"
#   backend/.venv/bin/python db/seed/demo/seed_demo.py --dsn "dbname=$DB"
companies=$(psql -tAX -d "$DB" -c "SELECT count(*) FROM company.companies")
echo "  companies    = $companies"
if [ "$companies" -gt 10 ]; then
  echo "  note: that is more than the demo seed creates - re-seed first if these" >&2
  echo "        are left over from a test run." >&2
fi

# Refuse to ship a snapshot that fails its own quality checks: restoring one
# would spread a known-bad corpus to every deployment.
failures=$(psql -tAX -d "$DB" -c \
  "SELECT count(*) FROM legal.v_quality_checks WHERE failing_rows > 0")
if [ "$failures" != "0" ]; then
  echo "error: $failures quality check(s) failing; fix them before snapshotting." >&2
  exit 1
fi

echo "→ recording applied migrations"
psql -q -v ON_ERROR_STOP=1 -d "$DB" -c "
CREATE TABLE IF NOT EXISTS public.schema_migrations (
  filename text PRIMARY KEY,
  applied_at timestamptz NOT NULL DEFAULT now());"
for f in ../migrations/0*.sql; do
  psql -q -d "$DB" -c "INSERT INTO public.schema_migrations (filename)
                       VALUES ('$(basename "$f")') ON CONFLICT DO NOTHING"
done

echo "→ dumping"
pg_dump --no-owner --no-acl --clean --if-exists -d "$DB" | gzip -9 > "$OUT.tmp"
mv "$OUT.tmp" "$OUT"

echo "  wrote $OUT ($(du -h "$OUT" | cut -f1))"
echo
echo "  Commit it, redeploy, and run ./db/snapshot/restore.sh on the target."
