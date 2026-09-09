"""Classification taxonomy and evidence-scored inference (brief §1, §6, §7, §18).

Every classifier returns (value, confidence, evidence). Confidence below
MIN_CONFIDENCE yields "UNKNOWN" plus a human-review flag rather than a guess
(brief §29). Evidence records *why*, so a reviewer can audit the call.
"""
import re

MIN_CONFIDENCE = 0.60

AUTHORITIES = ["MCA", "SEBI", "NSE", "BSE", "UNKNOWN"]

DOCUMENT_TYPES = {
    "MCA": ["ACT", "RULE", "NOTIFICATION", "CIRCULAR", "FORM", "INSTRUCTION_KIT", "FAQ", "AMENDMENT"],
    "SEBI": ["REGULATION", "MASTER_CIRCULAR", "CIRCULAR", "NOTIFICATION", "FAQ", "GUIDANCE"],
    "NSE": ["CHECKLIST", "CIRCULAR", "CORPORATE_ACTION_REQUIREMENT", "FILING_REQUIREMENT",
            "LISTING_REQUIREMENT", "XBRL_REQUIREMENT", "COMPLIANCE_CALENDAR", "NOTICE"],
    "BSE": ["CHECKLIST", "CIRCULAR", "CORPORATE_ACTION_REQUIREMENT", "FILING_REQUIREMENT",
            "LISTING_REQUIREMENT", "XBRL_REQUIREMENT", "COMPLIANCE_CALENDAR", "NOTICE"],
    "UNKNOWN": ["UNKNOWN"],
}

ISSUE_TYPES = ["RIGHTS", "PREFERENTIAL", "PRIVATE_PLACEMENT", "BONUS", "ESOP", "SWEAT_EQUITY",
               "PUBLIC_ISSUE", "FPO", "QIP", "CONVERSION", "WARRANTS", "OTHER", "GENERAL", "UNKNOWN"]

V1_ISSUE_TYPES = {"RIGHTS", "PREFERENTIAL", "PRIVATE_PLACEMENT"}

# Instrument kind drives which structural parser is applied.
INSTRUMENT_KINDS = ["ACT", "RULES", "REGULATIONS", "CIRCULAR", "CHECKLIST", "FAQ", "UNKNOWN"]


def normalise_name(filename):
    """Filenames use _ . - as separators, which are word characters to \\b.

    Without this, r"\\bInvIT\\b" never matches "Trading_Approval_InvITs" and the
    document is silently misclassified. Separators become spaces and plural
    forms are left for the patterns to handle.
    """
    return re.sub(r"[_\-.]+", " ", filename)


FILENAME_WEIGHT = 1.6   # a term in the title is stronger evidence than one in the body
HEADZONE_WEIGHT = 1.4   # the letterhead/title zone identifies the ISSUER
HEADZONE_CHARS = 1500


def _score(text, patterns):
    """Sum of weights for matched patterns, with the matched terms as evidence.

    One unambiguous match already carries most of a pattern's weight (0.7x);
    repetition saturates toward 1.0x. A term appearing once in a title is
    strong evidence, so frequency must not dominate specificity.
    """
    total, hits = 0.0, []
    for pat, weight in patterns:
        n = len(re.findall(pat, text, re.I))
        if n:
            total += weight * (0.7 + 0.3 * (1 - 0.5 ** (n - 1)))
            hits.append(f"{pat} x{n}")
    return total, hits


def _score_doc(filename, body, patterns):
    """Score filename, letterhead zone and body separately.

    Authority is about who ISSUED a document, not who it cites. An NSE
    checklist mentions "SEBI" a dozen times while citing LODR, but carries
    "National Stock Exchange of India Limited" on its letterhead. Weighting
    the opening zone above the body keeps citation frequency from
    overwhelming the issuer signal.
    """
    fs, fh = _score(normalise_name(filename), patterns)
    hs, hh = _score(body[:HEADZONE_CHARS], patterns)
    bs, bh = _score(body, patterns)
    hits = ([f"name:{h}" for h in fh] + [f"head:{h}" for h in hh] + [f"body:{h}" for h in bh])
    return fs * FILENAME_WEIGHT + hs * HEADZONE_WEIGHT + bs, hits


MIN_EVIDENCE = 1.2  # absolute score at which evidence is considered sufficient


def _decide(scored, floor=MIN_CONFIDENCE):
    """Pick the top-scoring label, or UNKNOWN when the call is not defensible.

    Confidence combines two independent things that must not be conflated:
      margin   - how far the winner leads the runner-up (is the choice clear?)
      strength - how much evidence exists at all (is there enough to decide?)
    A lone weak match has a perfect margin but no strength; two strong rivals
    have strength but no margin. Both must hold.
    """
    if not scored:
        return "UNKNOWN", 0.0, []
    name, (score, hits) = max(scored.items(), key=lambda kv: kv[1][0])
    others = sorted((v[0] for k, v in scored.items() if k != name), reverse=True)
    runner = others[0] if others else 0.0
    if score <= 0:
        return "UNKNOWN", 0.0, hits
    margin = score / (score + runner)
    strength = min(1.0, score / MIN_EVIDENCE)
    conf = min(0.99, margin * strength)
    if conf < floor:
        return "UNKNOWN", round(conf, 2), hits
    return name, round(conf, 2), hits


def classify_authority(filename, head_text):
    cands = {
        "SEBI": _score_doc(filename, head_text, [
            (r"securities and exchange board of india", 1.0), (r"\bSEBI\b", 0.45)]),
        # "Companies Act, 2013" is cited by nearly every SEBI regulation and NSE
        # checklist, so it is near-worthless as an authorship signal and is
        # weighted accordingly. Issuance is shown by the ministry's own name,
        # the rule-making formula, or an MCA rules title.
        "MCA": _score_doc(filename, head_text, [
            (r"ministry of corporate affairs", 1.2),
            (r"companies\s*\([^)]{3,60}\)\s*rules", 0.9),
            (r"in exercise of the powers conferred.{0,80}central government", 0.8),
            (r"\bRegistrar of Companies\b", 0.5), (r"\bMCA\b", 0.5),
            (r"companies act,?\s*2013", 0.25)]),
        "NSE": _score_doc(filename, head_text, [
            (r"national stock exchange of india limited", 1.4),
            (r"national stock exchange", 1.0), (r"\bNSE\b", 0.8), (r"NSE/CML", 0.9),
            (r"\bNSEIL\b", 0.8), (r"\bNEAPS\b", 0.9)]),
        "BSE": _score_doc(filename, head_text, [
            (r"\bBSE\s+limited\b", 1.4), (r"\bBSE\b", 0.8), (r"bombay stock exchange", 1.0),
            (r"bseindia", 0.9), (r"\bBSE\s+Listing\s+Centre\b", 1.2)]),
    }
    return _decide(cands)


def classify_document_type(authority, filename, head_text):
    rules = {
        # A SEBI regulation is *published via* a gazette notification, so both
        # words always co-occur. The short-title clause ("these regulations may
        # be called...") is what the instrument says about itself, and is the
        # only reliable discriminator between the instrument and its wrapper.
        "REGULATION": [(r"these regulations may be called", 1.6),
                       (r"hereby makes the following regulations", 1.4),
                       (r"regulations?,?\s*20\d\d", 1.0),
                       (r"\bICDR\b|\bLODR\b|\bSAST\b|\bPIT\b|\bSBEB\b", 0.9)],
        "MASTER_CIRCULAR": [(r"master circular", 1.4)],
        "CIRCULAR": [(r"\bcircular\b", 0.8), (r"NSE/CML/\d{4}", 1.0)],
        "NOTIFICATION": [(r"\bnotification\b", 0.7), (r"gazette of india", 0.6)],
        "FAQ": [(r"frequently asked questions", 1.3), (r"\bFAQ", 1.0)],
        "ACT": [(r"this act may be called", 1.6), (r"an act to consolidate", 1.2),
                (r"\bact,?\s*2013\b", 0.9)],
        "RULE": [(r"these rules may be called", 1.6),
                 (r"hereby makes the following rules", 1.4), (r"\brules,?\s*20\d\d\b", 1.1)],
        "FORM": [(r"\bform\s+(no\.?\s*)?(PAS|MGT|SH|INC)-?\d", 1.2)],
        "INSTRUCTION_KIT": [(r"instruction kit", 1.3)],
        "CHECKLIST": [(r"\bchecklist\b", 1.1), (r"list of (documents|details)", 1.0),
                      (r"documents\s*/?\s*details (required|to be submitted)", 1.0),
                      (r"Yes\s*/\s*No\s*/\s*Not Applicable", 1.2)],
        "GUIDANCE": [(r"points to (be )?remember", 1.3), (r"\bguidance\b", 0.8)],
        "LISTING_REQUIREMENT": [(r"listing application", 0.9), (r"trading approval", 1.0),
                                (r"in-?principle approval", 0.9)],
    }
    allowed = set(DOCUMENT_TYPES.get(authority, DOCUMENT_TYPES["UNKNOWN"]))
    scored = {}
    for dtype, pats in rules.items():
        if authority != "UNKNOWN" and dtype not in allowed:
            continue
        sc, h = _score_doc(filename, head_text, pats)
        if sc:
            scored[dtype] = (sc, h)
    return _decide(scored)


ISSUE_PATTERNS = {
    "RIGHTS": [(r"rights issue", 1.0), (r"rights entitlement", 1.0), (r"\bR-?WAP\b", 0.6)],
    "PREFERENTIAL": [(r"preferential (issue|allotment|basis)", 1.0)],
    "PRIVATE_PLACEMENT": [(r"private placement", 1.0), (r"\bPAS-4\b", 0.8), (r"\bPAS-5\b", 0.8)],
    "BONUS": [(r"bonus (issue|shares)", 1.0)],
    "ESOP": [(r"\bESOP\b", 1.0), (r"employee stock option", 1.0)],
    "SWEAT_EQUITY": [(r"sweat equity", 1.2)],
    "QIP": [(r"\bQIP\b", 1.0), (r"qualified institutions placement", 1.1)],
    "FPO": [(r"\bFPO\b", 1.0), (r"further public offer", 1.1)],
    "PUBLIC_ISSUE": [(r"\bIPO\b", 0.9), (r"initial public off", 1.0), (r"public issue", 0.8)],
    "CONVERSION": [(r"conversion of (securities|debentures|loan)", 1.0)],
    "WARRANTS": [(r"\bwarrants?\b", 0.7)],
}


def classify_issue_types(filename, text):
    """Multi-label: a document may cover several routes. Returns a ranked list.

    No match at all means the document is genuinely cross-cutting (LODR, PIT,
    SAST apply to every route), which is GENERAL - a fact, not an unknown.
    UNKNOWN is reserved for candidates that compete without clear separation.
    """
    found = []
    for itype, pats in ISSUE_PATTERNS.items():
        sc, h = _score_doc(filename, text, pats)
        if sc >= 0.5:
            found.append({"issue_type": itype, "score": round(sc, 2), "evidence": h})
    found.sort(key=lambda d: -d["score"])
    if not found:
        return [], "GENERAL", 0.9
    top, runner = found[0], (found[1]["score"] if len(found) > 1 else 0.0)
    conf = min(0.99, top["score"] / (top["score"] + runner + 0.35))
    primary = top["issue_type"] if conf >= MIN_CONFIDENCE else "UNKNOWN"
    return found, primary, round(conf, 2)


def classify_scope(filename, text):
    """REIT/InvIT documents are a different legal regime (units, not shares)."""
    name = normalise_name(filename)
    rx = r"\bREITs?\b|\bInvITs?\b|real estate investment trust|infrastructure investment trust"
    in_name = len(re.findall(rx, name, re.I))
    in_body = len(re.findall(rx, text[:6000], re.I))
    return ("REIT_INVIT", in_name + in_body) if (in_name >= 1 or in_body >= 2) else ("COMPANY", in_body)


def classify_instrument_kind(document_type):
    return {"ACT": "ACT", "RULE": "RULES", "REGULATION": "REGULATIONS",
            "CIRCULAR": "CIRCULAR", "MASTER_CIRCULAR": "CIRCULAR",
            "CHECKLIST": "CHECKLIST", "LISTING_REQUIREMENT": "CHECKLIST",
            "FAQ": "FAQ", "GUIDANCE": "CHECKLIST"}.get(document_type, "UNKNOWN")


REGULATORS = {"MCA", "SEBI", "NSE", "BSE", "RBI"}


def source_priority(authority, document_type):
    """P0 primary law .. P4 general web (brief §18).

    Priority follows what the document IS, then who issued it. A document from
    a regulator is never P4: P4 means the open web, and mislabelling an NSE
    checklist that way would bar genuine operational material from production.
    Where the type could not be determined but the issuer is a regulator, P2 is
    the honest floor; where even the issuer is unknown, P3 marks it as material
    that may not be the sole basis for a rule.
    """
    if document_type in ("ACT", "RULE", "REGULATION", "NOTIFICATION", "AMENDMENT"):
        return "P0"
    if document_type in ("MASTER_CIRCULAR", "CIRCULAR", "FAQ", "GUIDANCE"):
        return "P1"
    if document_type in ("INSTRUCTION_KIT", "CHECKLIST", "FORM", "LISTING_REQUIREMENT",
                         "CORPORATE_ACTION_REQUIREMENT", "FILING_REQUIREMENT",
                         "XBRL_REQUIREMENT", "COMPLIANCE_CALENDAR", "NOTICE"):
        return "P2"
    if authority in REGULATORS:
        return "P2"
    return "P3"


DATE_PATTERNS = [
    re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(January|February|March|April|May|June|July|August|"
               r"September|October|November|December),?\s+(\d{4})\b", re.I),
    re.compile(r"\b(January|February|March|April|May|June|July|August|September|October|"
               r"November|December)\s+(\d{1,2}),?\s+(\d{4})\b", re.I),
]
MONTHS = {m.lower(): i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August",
     "September", "October", "November", "December"], start=1)}


def find_dates(text):
    """Dates parsed from document *text* only - never from filesystem mtime."""
    out = []
    for rx in DATE_PATTERNS:
        for m in rx.finditer(text):
            g = m.groups()
            try:
                if g[0].lower() in MONTHS:
                    mon, day, yr = MONTHS[g[0].lower()], int(g[1]), int(g[2])
                else:
                    day, mon, yr = int(g[0]), MONTHS[g[1].lower()], int(g[2])
                if 1950 <= yr <= 2100 and 1 <= day <= 31:
                    out.append({"iso": f"{yr:04d}-{mon:02d}-{day:02d}", "raw": m.group(0)})
            except (KeyError, ValueError):
                continue
    return out
