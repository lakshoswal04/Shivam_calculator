#!/usr/bin/env bash
# Start the platform for development: FastAPI on :8000, Next.js on :3000.
set -euo pipefail
cd "$(dirname "$0")"

case "${1:-up}" in
  up)
    echo "→ API   http://localhost:8000/docs"
    echo "→ Web   http://localhost:3000"
    ( cd backend  && .venv/bin/uvicorn app.main:app --reload --port 8000 ) &
    ( cd frontend && npm run dev -- --port 3000 ) &
    wait
    ;;
  db)
    # Rebuild the database from migrations, corpus, authored rules and demo data.
    DB="${LEGAL_DB:-legal_rules_dev}"
    dropdb --if-exists "$DB"; createdb "$DB"
    for f in db/migrations/0*.sql; do psql -v ON_ERROR_STOP=1 -q -d "$DB" -f "$f"; echo "  applied $f"; done
    ./.venv/bin/python pipeline/p06_load.py --dsn "dbname=$DB"
    backend/.venv/bin/python pipeline/p08_load_rules.py --dsn "dbname=$DB"
    backend/.venv/bin/python db/seed/demo/seed_demo.py --dsn "dbname=$DB"
    ;;
  test)
    # Report every check rather than stopping at the first non-zero exit.
    set +e
    echo "== pipeline =="; ./.venv/bin/python -m pytest pipeline/tests -q
    echo "== backend  =="; ( cd backend && .venv/bin/python -m pytest tests -q )
    echo "== schema guarantees =="
    psql -q -d legal_rules_dev -f db/tests/constraint_tests.sql 2>&1 | sed -n 's/.*NOTICE:  /  /p'
    echo "== tenant isolation =="
    PGPASSWORD=calcapp_dev_pw psql -q -h localhost -U calcapp -d legal_rules_dev \
      -f db/tests/rls_isolation_test.sql 2>&1 | grep -cE 'PASS' | xargs echo "  checks passed:"
    echo "== data quality =="
    psql -tA -d legal_rules_dev -c \
      "SELECT check_name||' = '||failing_rows FROM legal.v_quality_checks WHERE failing_rows>0;" \
      | sed 's/^/  FAIL /' || true
    psql -tA -d legal_rules_dev -c \
      "SELECT '  all quality checks clear' WHERE NOT EXISTS
       (SELECT 1 FROM legal.v_quality_checks WHERE failing_rows>0);"
    echo "== frontend typecheck =="
    ( cd frontend && npx tsc --noEmit && echo "  clean" )
    ;;
  purge-demo)
    backend/.venv/bin/python db/seed/demo/seed_demo.py --purge
    ;;
  *) echo "usage: ./dev.sh [up|db|test|purge-demo]"; exit 1 ;;
esac
