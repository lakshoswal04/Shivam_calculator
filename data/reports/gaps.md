# Source Gaps

_Generated 2026-09-06T21:39:55+00:00_

Provisions that V1 needs but that no supplied document covers. Rules depending on these are not authored (brief §29).

## COMPANIES_ACT_2013  
**Severity:** BLOCKER  
**Why:** Primary law (P0) for the V1 routes. Every official channel tried refused automated access: mca.gov.in returns HTTP 403 to scripted clients, and indiacode.gov.in presents a certificate that does not match its hostname and serves a JavaScript shell instead of the PDF.  
**Action:** Download the Companies Act, 2013 **as amended to date** manually and place it in corpus/originals/, then re-run p00_inventory.py. As-enacted text is not sufficient: section 42 was wholly substituted by the Companies (Amendment) Act, 2017 w.e.f. 07-08-2018.  
**Sections required:** 23, 39, 42, 55, 62, 63, 117, 179(3)(c)  
**Blocks routes:** PRIVATE_PLACEMENT, RIGHTS  

## MCA_FORM_INSTRUCTION_KITS  
**Severity:** GAP  
**Why:** PAS-3, MGT-14, SH-7 instruction kits absent; needed for filing field-level rules.  
**Action:** Supply the document, or leave dependent rules unauthored.  

## SEBI_CIRCULARS_AND_MASTER_CIRCULARS  
**Severity:** GAP  
**Why:** Absent; ICDR/LODR operational clarifications rest on these.  
**Action:** Supply the document, or leave dependent rules unauthored.  

## NSE_CIRCULAR_NSE_CML_2023_51  
**Severity:** GAP  
**Why:** Cited by 'Points to remember_28(1)' as gating the >Rs.100cr preferential issue-summary requirement, but not supplied.  
**Action:** Supply the document, or leave dependent rules unauthored.  

## V1 route coverage

| Route | Documents | Primary law (MCA/SEBI) |
|---|---|---|
| PREFERENTIAL | 16 | 6 |
| PRIVATE_PLACEMENT | 8 | 4 |
| RIGHTS | 12 | 6 |