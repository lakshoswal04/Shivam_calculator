"""Issue-route manifests (PRD §12).

Declares, per route: which questions the wizard asks, which facts the engines
need, and whether the route is gated on a source the corpus does not yet have.

Source gates are data, not code branches: a gate lifts when the missing
document is ingested and its rules approved, without editing this file beyond
removing the entry.
"""
from typing import Optional

V1_ROUTES = ["RIGHTS", "PREFERENTIAL", "PRIVATE_PLACEMENT"]

ALL_ROUTES = [
    "RIGHTS", "PREFERENTIAL", "PRIVATE_PLACEMENT", "BONUS", "ESOP", "SWEAT_EQUITY",
    "PUBLIC_ISSUE", "FPO", "QIP", "CONVERSION", "WARRANTS", "OTHER",
]

# Routes whose primary law is absent. The route still runs every calculation;
# its legal conclusions return REVIEW_REQUIRED naming what is missing.
SOURCE_GATES: dict[str, dict] = {
    "PRIVATE_PLACEMENT": {
        "code": "COMPANIES_ACT_2013",
        "provisions_required": ["42", "39", "23", "117", "179(3)(c)"],
        "detail": ("Section 42 of the Companies Act, 2013 governs private placement and is "
                   "not in the source corpus. It must be the text as amended: section 42 was "
                   "wholly substituted by the Companies (Amendment) Act, 2017 w.e.f. "
                   "07-08-2018, so as-enacted text would produce wrong rules."),
    },
    "RIGHTS": {
        "code": "COMPANIES_ACT_2013",
        "provisions_required": ["62(1)(a)", "62(2)", "23"],
        "detail": ("Section 62 of the Companies Act, 2013 is the legal basis of a rights "
                   "issue and is not in the source corpus. SEBI ICDR Chapter III rules for "
                   "listed issuers are available and are applied."),
    },
}

ROUTE_LABELS = {
    "RIGHTS": "Rights Issue",
    "PREFERENTIAL": "Preferential Issue",
    "PRIVATE_PLACEMENT": "Private Placement",
    "BONUS": "Bonus Issue",
    "ESOP": "Employee Stock Options",
    "SWEAT_EQUITY": "Sweat Equity",
    "PUBLIC_ISSUE": "Public Issue / IPO",
    "FPO": "Further Public Offer",
    "QIP": "Qualified Institutions Placement",
    "CONVERSION": "Conversion of Securities",
    "WARRANTS": "Warrants",
    "OTHER": "Other securities",
}

# Route-conditional questions. `listed_only` fields are hidden for unlisted
# issuers, so a private company is never shown exchange questions.
ROUTE_QUESTIONS: dict[str, list[dict]] = {
    "RIGHTS": [
        {"key": "eligible_shares", "label": "Eligible shares as on record date",
         "type": "number", "unit": "shares", "required": True},
        {"key": "rights_ratio_num", "label": "Rights ratio — new shares offered",
         "type": "number", "required": True},
        {"key": "rights_ratio_den", "label": "Rights ratio — for every N held",
         "type": "number", "required": True},
        {"key": "record_date", "label": "Record date", "type": "date"},
        {"key": "renunciation_permitted", "label": "Is renunciation permitted?",
         "type": "boolean"},
        {"key": "issue_open_date", "label": "Issue opens", "type": "date"},
        {"key": "issue_close_date", "label": "Issue closes", "type": "date"},
        {"key": "oversubscription_allowed", "label": "Applications for additional shares allowed?",
         "type": "boolean"},
        {"key": "letter_of_offer_filed", "label": "Letter of offer filed with the exchange?",
         "type": "boolean", "listed_only": True},
        # Read by RGT-L-001 (ICDR reg. 61). Without it the engine cannot judge
        # eligibility and returns REVIEW_REQUIRED rather than assuming.
        {"key": "company_debarred_from_capital_market",
         "label": "Is the issuer, any promoter or any director debarred from accessing the capital market?",
         "type": "boolean", "required": True, "listed_only": True},
    ],
    "PREFERENTIAL": [
        {"key": "relevant_date", "label": "Relevant date (for pricing)", "type": "date",
         "required": True},
        {"key": "special_resolution_date", "label": "Date of special resolution",
         "type": "date"},
        {"key": "consideration_type", "label": "Consideration",
         "type": "select", "options": ["CASH", "NON_CASH", "SWAP", "DEBT_CONVERSION"],
         "required": True},
        {"key": "valuation_report_date", "label": "Date of valuation report", "type": "date"},
        {"key": "valuation_by", "label": "Valuation carried out by",
         "type": "select", "options": ["REGISTERED_VALUER", "MERCHANT_BANKER",
                                       "PRACTISING_CA", "NOT_OBTAINED"]},
        {"key": "allottee_count", "label": "Number of proposed allottees", "type": "number",
         "required": True},
        {"key": "any_allottee_is_promoter", "label": "Is any allottee a promoter or in the promoter group?",
         "type": "boolean", "required": True},
        {"key": "any_allottee_is_related_party", "label": "Is any allottee a related party?",
         "type": "boolean"},
        {"key": "results_in_change_of_control", "label": "Will the issue result in a change of control?",
         "type": "boolean", "listed_only": True},
        {"key": "all_allottees_demat", "label": "Are all allottees' existing holdings in demat form?",
         "type": "boolean", "listed_only": True},
        {"key": "listed_trading_days", "label": "Trading days the shares have been listed",
         "type": "number", "listed_only": True},
        # Needed by the reg.162A(1) proviso, which excepts banks, public financial
        # institutions and insurers from the monitoring-agency requirement. Without
        # it the engine cannot tell whether the exception applies and correctly
        # returns REVIEW_REQUIRED, so the question has to be asked.
        {"key": "company_entity_class", "label": "What kind of entity is the issuer?",
         "type": "select", "required": True,
         "options": ["ORDINARY_COMPANY", "BANK", "PUBLIC_FINANCIAL_INSTITUTION",
                     "INSURANCE_COMPANY"]},
        {"key": "monitoring_agency_appointed",
         "label": "Has a registered credit rating agency been appointed to monitor use of proceeds?",
         "type": "boolean"},
        {"key": "lock_in_confirmed",
         "label": "Have the allottees confirmed the allotted securities will be locked in?",
         "type": "boolean"},
        {"key": "fully_paid_at_allotment",
         "label": "Will the shares be fully paid up at the time of allotment?",
         "type": "boolean", "required": True},
        {"key": "explanatory_statement_prepared",
         "label": "Has the explanatory statement with the prescribed disclosures been prepared?",
         "type": "boolean"},
        {"key": "floor_price_determined",
         "label": "Minimum price determined under regulation 164 (if computed)",
         "type": "text", "listed_only": True},
        {"key": "in_principle_approval_date", "label": "Exchange in-principle approval date",
         "type": "date", "listed_only": True},
    ],
    "PRIVATE_PLACEMENT": [
        {"key": "identified_persons_count", "label": "Number of identified persons in this offer",
         "type": "number", "required": True},
        {"key": "persons_in_financial_year", "label": "Persons already allotted under private placement this financial year",
         "type": "number"},
        {"key": "offer_letter_date", "label": "Date the offer letter (PAS-4) was circulated",
         "type": "date"},
        {"key": "separate_bank_account", "label": "Is subscription money held in a separate bank account?",
         "type": "boolean", "required": True},
        {"key": "consideration_type", "label": "Consideration",
         "type": "select", "options": ["CASH", "NON_CASH", "DEBT_CONVERSION"], "required": True},
        {"key": "previous_offer_closed", "label": "Has any previous private placement offer been completed or withdrawn?",
         "type": "boolean"},
        {"key": "proposed_allotment_date", "label": "Proposed allotment date", "type": "date"},
    ],
}


def questions_for(route: str, listed: bool) -> list[dict]:
    """Only the questions this route and listing status actually need."""
    return [q for q in ROUTE_QUESTIONS.get(route, [])
            if listed or not q.get("listed_only")]


def gate_for(route: str) -> Optional[dict]:
    return SOURCE_GATES.get(route)


def candidate_routes(facts: dict) -> list[dict]:
    """Route guidance for a user who selected "Not Sure" (PRD FR-ROUTE-002).

    Describes which routes may be relevant and what distinguishes them. It
    deliberately stops short of a legal determination: the result is always
    REVIEW_REQUIRED and recommends professional confirmation.
    """
    issue = facts.get("issue", {}) or {}
    company = facts.get("company", {}) or {}
    listed = company.get("listed_status") == "LISTED"
    allottees = issue.get("allottee_count") or issue.get("identified_persons_count")
    to_existing = issue.get("offered_to_existing_shareholders")

    out = []
    if to_existing is True:
        out.append(("RIGHTS", 3,
                    "The securities are offered to existing shareholders in proportion to "
                    "their holding, which is the defining feature of a rights issue."))
    elif to_existing is None:
        out.append(("RIGHTS", 1,
                    "Consider a rights issue if the offer goes to existing shareholders in "
                    "proportion to their holdings."))
    if listed:
        out.append(("PREFERENTIAL", 3 if to_existing is False else 2,
                    "A listed issuer allotting to selected persons on a preferential basis "
                    "falls under SEBI ICDR Chapter V."))
    else:
        out.append(("PREFERENTIAL", 2,
                    "An unlisted company allotting to selected persons may be making a "
                    "preferential offer under the Share Capital and Debentures Rules."))
        out.append(("PRIVATE_PLACEMENT", 2 if (allottees or 0) else 1,
                    "An offer to a identified group of persons, rather than to the public or "
                    "to all shareholders, may be a private placement."))
    if (allottees or 0) and int(allottees) > 0 and not listed:
        for i, (code, score, why) in enumerate(out):
            if code == "PRIVATE_PLACEMENT":
                out[i] = (code, score + 1, why)

    out.sort(key=lambda t: -t[1])
    return [{"issue_type": c, "label": ROUTE_LABELS[c], "relevance": s, "rationale": w,
             "source_gate": gate_for(c)} for c, s, w in out]
