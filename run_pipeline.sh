#!/usr/bin/env bash
# End-to-end Pass 1 pipeline. Safe to re-run: every stage is idempotent and
# originals are opened read-only.
set -euo pipefail
cd "$(dirname "$0")"
PY=./.venv/bin/python
DB="${LEGAL_DB:-legal_rules_dev}"

echo "== 0. inventory ==";       $PY pipeline/p00_inventory.py
echo "== 1. acquisition ==";     $PY pipeline/p01_acquire.py
echo "== 0b. re-inventory ==";   $PY pipeline/p00_inventory.py >/dev/null
echo "== 2. extraction ==";      $PY pipeline/p02_extract.py
echo "== 3. applicability ==";   $PY pipeline/p03_classify.py
echo "== 4. structure ==";       $PY pipeline/p04_structure.py
echo "== migrations ==";         dropdb --if-exists "$DB"; createdb "$DB"
for f in db/migrations/0*.sql; do psql -v ON_ERROR_STOP=1 -q -d "$DB" -f "$f"; echo "   applied $f"; done
echo "== 6. load ==";            $PY pipeline/p06_load.py --dsn "dbname=$DB"
echo "== 7. export ==";          $PY pipeline/p07_export.py
echo "== tests ==";              $PY -m pytest pipeline/tests -q
# psql prefixes notices with "psql:<file>:<line>: "; grep returning no match
# must not abort the run, hence the `|| true`.
echo "== schema guarantees =="
psql -q -d "$DB" -f db/tests/constraint_tests.sql 2>&1 \
  | sed -n 's/.*NOTICE:  /   /p; s/.*WARNING:  /   !! /p' || true
echo "== 8. rules ==";          backend/.venv/bin/python pipeline/p08_load_rules.py --dsn "dbname=$DB"
echo "== 5. validation ==";      $PY pipeline/p05_validate.py --dsn "dbname=$DB"
