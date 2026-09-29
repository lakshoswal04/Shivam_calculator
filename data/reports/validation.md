# Validation Report

_Generated 2026-09-29T09:03:28+00:00_

**32/33 checks passed** (0 hard failures, 1 soft).

| Result | Severity | Check | Detail |
|---|---|---|---|
| PASS | HARD | every inventoried file exists on disk |  |
| PASS | HARD | originals unchanged since inventory (SHA-256 re-verified) |  |
| PASS | SOFT | original files are read-only |  |
| PASS | HARD | no duplicate document_id |  |
| PASS | SOFT | no duplicate file_hash | 0 duplicate(s) |
| PASS | HARD | every in-force COMPANY-scope document was extracted |  |
| PASS | HARD | no deferred document was extracted |  |
| PASS | HARD | PDF page counts reconcile with extraction |  |
| FAIL | SOFT | no silently empty page | 1: MCA Instruction Kit SH-7.pdf p.25 |
| PASS | SOFT | low-text pages are flagged, not silently OCR'd | 40 page(s) flagged: SEBI_MC_20101231_Master_circular_for_Exchange_Traded_Derivatives.pdf p.94; SEBI_MC_20130401_Master_Circular_on_Matters_relating_to_Exchange_Traded_Der |
| PASS | HARD | no provision points beyond its document's page count | 0 |
| PASS | SOFT | every provision carries a citation and page anchor | 0 provision(s) with neither heading nor body |
| PASS | SOFT | citation ambiguity is measured and flagged | 8509/20890 (40.7%) flagged - Schedules restart numbering; citation_uid remains unique |
| PASS | HARD | db: approval_without_rule | 0 row(s) |
| PASS | HARD | db: approved_rule_on_superseded_source | 0 row(s) |
| PASS | HARD | db: approved_rule_still_flagged | 0 row(s) |
| PASS | HARD | db: calculation_without_inputs | 0 row(s) |
| PASS | HARD | db: deadline_without_anchor | 0 row(s) |
| PASS | HARD | db: exception_without_rule | 0 row(s) |
| PASS | HARD | db: filing_without_trigger | 0 row(s) |
| PASS | HARD | db: open_conflicts | 0 row(s) |
| PASS | HARD | db: pending_rule_in_production_view | 0 row(s) |
| PASS | HARD | db: provision_page_out_of_range | 0 row(s) |
| PASS | HARD | db: rule_without_effective_from | 0 row(s) |
| PASS | HARD | db: rule_without_provision_anchor | 0 row(s) |
| PASS | HARD | db: rule_without_source | 0 row(s) |
| PASS | HARD | db: source_without_document | 0 row(s) |
| PASS | HARD | db: supersession_chain_broken | 0 row(s) |
| PASS | HARD | db: no rule reaches production without human approval | 0 active (expected 0 in Pass 1) |
| PASS | HARD | db: provision pages within document bounds |  |
| PASS | SOFT | V1 route RIGHTS has at least one primary-law source | 24 document(s), 18 from MCA/SEBI |
| PASS | SOFT | V1 route PRIVATE_PLACEMENT has at least one primary-law source | 21 document(s), 17 from MCA/SEBI |
| PASS | SOFT | V1 route PREFERENTIAL has at least one primary-law source | 23 document(s), 13 from MCA/SEBI |

## Corpus

- Documents inventoried: **190** (89 COMPANY, 101 REIT/InvIT deferred)
- Provisions extracted: **20,890**
- Pages flagged for human review: **40**

## Database quality checks (brief §27)

| Check | Failing rows |
|---|---|
| approval_without_rule | 0 |
| approved_rule_on_superseded_source | 0 |
| approved_rule_still_flagged | 0 |
| calculation_without_inputs | 0 |
| deadline_without_anchor | 0 |
| exception_without_rule | 0 |
| filing_without_trigger | 0 |
| open_conflicts | 0 |
| pending_rule_in_production_view | 0 |
| provision_page_out_of_range | 0 |
| rule_without_effective_from | 0 |
| rule_without_provision_anchor | 0 |
| rule_without_source | 0 |
| source_without_document | 0 |
| supersession_chain_broken | 0 |
