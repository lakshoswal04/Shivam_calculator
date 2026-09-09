# Corporate Securities Issue Assessment, Compliance & Calculation Platform

A platform for Indian companies proposing to issue additional shares or securities. It
reports **capital capacity** (arithmetic) and **legal issue capacity** (what the approved
rules permit) as two separate answers, and traces every legal conclusion to an exact
provision, page and source document.

**Stack:** Next.js 16 · FastAPI · PostgreSQL 15+
**Spec:** [`docs/PRD.md`](docs/PRD.md) — 47 sections, 85 requirements

---

## Quick start

```bash
./dev.sh db      # rebuild database: migrations → corpus → rules → demo data
./dev.sh up      # API on :8000, web on :3000
./dev.sh test    # every test and guarantee
```

Sign in at http://localhost:3000 with `cs@demo.test` / `demo1234`
(also `cfo@`, `legal@`, `owner@` for the other roles).

---

## Layout

```
backend/       FastAPI · Python 3.12 · engines, API, tests
frontend/      Next.js 16 · TypeScript · Tailwind v4
db/migrations/ 001–011, forward-only, each with a rollback block
db/seed/rules/ authored legal rules as versioned YAML
db/tests/      schema guarantees and tenant-isolation tests
pipeline/      document ingestion p00–p08 (built in an earlier pass)
corpus/        original source documents, read-only, hash-verified
docs/PRD.md    the specification
```

`backend/` and `frontend/` are wholly separate; they share nothing but the HTTP contract.

---

## What it does

**Capital capacity vs legal issue capacity.** The distinction is the product. Unused
authorised capital is arithmetic; whether the company may lawfully issue against it is a
legal question with a different answer. They are separate fields in the API, separate
figures in the UI, and never merged.

**A missing fact is not `false`.** If a rule needs a fact the user did not supply, the
result is `REVIEW_REQUIRED` naming the field — never a defaulted answer. Legal capacity is
then reported as `null` with the causes named, not as a number.

**Every conclusion traces to law.** A rule result carries its provision, page, source
document, SHA-256 and reviewer. The provision text is shown inline.

```
PREF-L-004  Monitoring agency for an issue above one hundred crore rupees   BLOCKED
  § SEBI (ICDR) Regulations, 2018, reg. 162A(1) · p.127 · P0 · db196f1f33dc…
```

**Exceptions are evaluated after conditions.** A rule that applies but is excepted is not
the same as a rule that never applied. The reg. 162A(1) proviso, for instance, excepts a
bank from the monitoring-agency requirement — and the engine says so, naming the exception.

---

## Rule content

15 rules across three routes, each anchored to a real provision with its requirement text
quoted from the source:

| Route | Rules | Instrument |
|---|---|---|
| Preferential (listed) | 8 | SEBI (ICDR) Regulations, 2018, Ch. V |
| Preferential (unlisted) | 3 | Companies (Share Capital and Debentures) Rules, 2014, r.13 |
| Rights (listed) | 2 | SEBI (ICDR) Regulations, 2018, Ch. III |
| Private placement | 2 | Companies (Prospectus and Allotment) Rules, 2014, r.14 |

Rules live in `db/seed/rules/**.yaml` and load via `pipeline/p08_load_rules.py`, which
resolves every citation against the provision tree and refuses to load a rule whose anchor
is unresolvable or ambiguous. A rule change is a data operation, never a deployment.

### Source gaps

The **Companies Act, 2013 is not in the corpus** and cannot be fetched (mca.gov.in returns
403 to scripted clients; indiacode.gov.in serves a hostname-mismatched certificate and then
a JavaScript shell). This gates two of the three MVP routes:

- **Private placement** — s.42 is the governing provision.
- **Rights** — s.62 is the legal basis of the entitlement.

Both routes still run every calculation and return `REVIEW_REQUIRED` on the Act-dependent
legal limbs, naming the missing sections. **Preferential is the one route not Act-gated**,
because ICDR Ch. V and SCD r.13 are both in hand.

Supply the Act **as amended** into `corpus/originals/` and re-run `./dev.sh db`. As-enacted
text is not enough: s.42 was wholly substituted by the Companies (Amendment) Act, 2017
w.e.f. 07-08-2018, and a database trigger refuses to approve a rule sourced from
`REFERENCE_ONLY` text.

---

## Governance

No rule reaches production without a named human reviewer. The database enforces it:

```sql
CONSTRAINT approved_needs_reviewer
  CHECK (legal_review_status <> 'APPROVED'
         OR (reviewer_id IS NOT NULL AND reviewed_at IS NOT NULL))
```

The engine reads only `legal.v_active_rule_versions` — approved, inside its validity
window, no unresolved conflict.

**The demo seed is not legal sign-off.** It approves rules under a `demo-reviewer` identity
so the platform can be exercised end to end. Every such rule is marked `demo_approved` in
the payload and labelled in the UI. Purge with `./dev.sh purge-demo`.

Real review happens in the admin portal (`/admin`), which shows each drafted rule beside
the provision it was drawn from.

---

## Guarantees the database enforces

Verified by `db/tests/constraint_tests.sql` (12 checks) and
`db/tests/rls_isolation_test.sql` (7 checks):

| Guarantee | Mechanism |
|---|---|
| Two versions of one rule can never cover the same date | `EXCLUDE USING gist (rule_id WITH =, validity WITH &&)` |
| No approval without a named reviewer | `CHECK` |
| No approval on a P3/P4 or `REFERENCE_ONLY` source | `BEFORE` trigger |
| Malformed condition ASTs cannot be stored | `CHECK legal.validate_condition_ast()` |
| Paid-up ≤ subscribed ≤ issued ≤ authorised | `CHECK` chain |
| One tenant cannot read or write another's data | Row-level security, `FORCE`d |
| A filing cannot exist without a trigger event | FK to `legal.anchor_events` |
| An approval cannot exist without a causing rule | `NOT NULL` FK |

**Row-level security only works because the API connects as `calcapp`**, an ordinary role.
Superusers and `BYPASSRLS` roles ignore policies entirely, which makes isolation silently
inert. Migration `008` creates that role; do not point `DATABASE_URL` at a superuser.

---

## Tests

```bash
./dev.sh test
```

- **pipeline** — 38 tests: hashing, cleaning, citation parsing, amendment markers,
  SQL↔Python AST parity
- **backend** — 22 tests: calculation truth tables, dual-capacity separation,
  `REVIEW_REQUIRED` on missing facts, statutory exception override, reproducibility,
  RBAC matrix, tenant isolation, source-gate honesty
- **schema guarantees** — 12 negative tests that must fail
- **tenant isolation** — 7 checks, run as the application role
- **data quality** — `legal.v_quality_checks` must return zero failing rows
- **manifest coverage** — every fact any rule reads must be collectable by its route's
  wizard, so a rule can never be permanently unevaluable

---

## Not built yet

MFA and SSO · what-if simulator (schema supports it) · PDF report export · bonus, ESOP,
sweat equity, IPO, FPO, QIP routes · BSE rule content beyond the four acquired documents ·
notification delivery.
