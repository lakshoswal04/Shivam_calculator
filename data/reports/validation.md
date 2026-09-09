# Validation Report

_Generated 2026-09-06T21:39:55+00:00_

**30/31 checks passed** (0 hard failures, 1 soft).

| Result | Severity | Check | Detail |
|---|---|---|---|
| PASS | HARD | every inventoried file exists on disk |  |
| PASS | HARD | originals unchanged since inventory (SHA-256 re-verified) |  |
| PASS | SOFT | original files are read-only |  |
| PASS | HARD | no duplicate document_id |  |
| PASS | SOFT | no duplicate file_hash | 0 duplicate(s) |
| PASS | HARD | every COMPANY-scope document was extracted |  |
| PASS | HARD | PDF page counts reconcile with extraction |  |
| PASS | SOFT | no silently empty page | 0:  |
| PASS | SOFT | low-text pages are flagged, not silently OCR'd | 4 page(s) flagged: SEBI ICDR Regulations.pdf p.360; SEBI ICDR Regulations.pdf p.362; SEBI ICDR Regulations.pdf p.363; SEBI ICDR Regulations.pdf p.364 |
| PASS | HARD | no provision points beyond its document's page count | 0 |
| FAIL | SOFT | every provision carries a citation and page anchor | 1 provision(s) with neither heading nor body |
| PASS | SOFT | citation ambiguity is measured and flagged | 2104/7454 (28.2%) flagged - Schedules restart numbering; citation_uid remains unique |
| PASS | HARD | db: ambiguous_citation_used_by_rule | 0 row(s) |
| PASS | HARD | db: approval_without_rule | 0 row(s) |
| PASS | HARD | db: approved_rule_still_flagged | 0 row(s) |
| PASS | HARD | db: calculation_without_inputs | 0 row(s) |
| PASS | HARD | db: deadline_without_anchor | 0 row(s) |
| PASS | HARD | db: exception_without_rule | 0 row(s) |
| PASS | HARD | db: filing_without_trigger | 0 row(s) |
| PASS | HARD | db: open_conflicts | 0 row(s) |
| PASS | HARD | db: pending_rule_in_production_view | 0 row(s) |
| PASS | HARD | db: provision_page_out_of_range | 0 row(s) |
| PASS | HARD | db: rule_without_effective_from | 0 row(s) |
| PASS | HARD | db: rule_without_provision | 0 row(s) |
| PASS | HARD | db: rule_without_source | 0 row(s) |
| PASS | HARD | db: source_without_document | 0 row(s) |
| PASS | HARD | db: no rule reaches production without human approval | 0 active (expected 0 in Pass 1) |
| PASS | HARD | db: provision pages within document bounds |  |
| PASS | SOFT | V1 route PREFERENTIAL has at least one primary-law source | 16 document(s), 6 from MCA/SEBI |
| PASS | SOFT | V1 route PRIVATE_PLACEMENT has at least one primary-law source | 8 document(s), 4 from MCA/SEBI |
| PASS | SOFT | V1 route RIGHTS has at least one primary-law source | 12 document(s), 6 from MCA/SEBI |

## Corpus

- Documents inventoried: **53** (39 COMPANY, 14 REIT/InvIT deferred)
- Provisions extracted: **7,454**
- Pages flagged for human review: **4**

## Database quality checks (brief §27)

| Check | Failing rows |
|---|---|
| ambiguous_citation_used_by_rule | 0 |
| approval_without_rule | 0 |
| approved_rule_still_flagged | 0 |
| calculation_without_inputs | 0 |
| deadline_without_anchor | 0 |
| exception_without_rule | 0 |
| filing_without_trigger | 0 |
| open_conflicts | 0 |
| pending_rule_in_production_view | 0 |
| provision_page_out_of_range | 0 |
| rule_without_effective_from | 0 |
| rule_without_provision | 0 |
| rule_without_source | 0 |
| source_without_document | 0 |
