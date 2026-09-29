"""Tests for hashing, cleaning and citation parsing."""
import json
import subprocess
from pathlib import Path

import pytest

from lib.cleaning import clean_page, find_running_headers, repair_hyphenation
from lib.citations import parse_provisions, build_citation, extract_references
from lib.hashing import sha256_text, doc_id_for
from lib import conditions as C
from lib import supersession as S

ROOT = Path(__file__).resolve().parent.parent.parent


# ------------------------------------------------------------------ hashing
def test_hash_is_deterministic():
    assert sha256_text("section 62") == sha256_text("section 62")
    assert sha256_text("section 62") != sha256_text("section 63")


def test_doc_id_stable_and_slugged():
    a = doc_id_for("SEBI ICDR Regulations.pdf", "ab" * 32)
    assert a == doc_id_for("SEBI ICDR Regulations.pdf", "ab" * 32)
    assert a.startswith("sebi-icdr-regulations-")


# ----------------------------------------------------------------- cleaning
def test_hyphenation_repaired_across_line_breaks():
    assert repair_hyphenation("prefer-\nential") == "preferential"


def test_cleaning_never_empties_a_page_with_content():
    """Regression: a repeated signature block once reduced a page to nothing."""
    boiler = {"Non-Confidential", "Yours faithfully,"}
    out = clean_page("Non-Confidential\nYours faithfully,\n", boiler)
    assert out.strip(), "cleaning removed all content from a non-empty page"


def test_running_headers_need_enough_pages():
    # With only 3 pages, repetition is not yet evidence of boilerplate.
    assert find_running_headers(["X\nbody", "X\nbody", "X\nbody"]) == set()
    pages = ["HEADER\nbody %d" % i for i in range(8)]
    assert "HEADER" in find_running_headers(pages)


def test_cleaning_preserves_legal_wording():
    raw = "The issuer shall not allot securities unless the special resolution is passed."
    assert clean_page(raw) == raw


# ---------------------------------------------------------------- citations
def _pages(text):
    return [{"page_no": 1, "cleaned_text": text}]


def test_regulation_with_inline_subunit_is_split():
    provs = parse_provisions(_pages(
        "164. (1) If the equity shares have been listed for 90 trading days\n"
        "(2) Where the shares are not frequently traded\n"), "REGULATIONS")
    types = [(p.provision_type, p.number) for p in provs]
    assert ("REGULATION", "164") in types
    assert ("SUB_REGULATION", "1") in types
    assert ("SUB_REGULATION", "2") in types


def test_amendment_marker_does_not_hide_a_provision():
    """SEBI gazette text embeds footnote markers: '166. 335[(1)] The price ...'"""
    provs = parse_provisions(_pages("166. 335[(1)] The price determined shall be\n"),
                             "REGULATIONS")
    assert any(p.provision_type == "REGULATION" and p.number == "166" for p in provs)


def test_amendment_markers_are_captured_not_years():
    provs = parse_provisions(_pages(
        "164. (1) a period of 305[90 trading days] under the Act, 1992 shall apply\n"),
        "REGULATIONS")
    markers = {m for p in provs for m in p.amendment_markers}
    assert "305" in markers
    assert "1992" not in markers, "a year was misread as an amendment footnote"


def test_numbered_list_is_not_a_provision():
    provs = parse_provisions(_pages("2. 5 lakh rupees shall be paid\n"), "REGULATIONS")
    assert not any(p.provision_type == "REGULATION" for p in provs)


def test_schedule_paragraphs_are_not_regulations():
    provs = parse_provisions(_pages(
        "SCHEDULE I\n1. This paragraph sits inside a schedule\n"), "REGULATIONS")
    assert any(p.provision_type == "SCHEDULE" for p in provs)
    assert not any(p.provision_type == "REGULATION" for p in provs)


def _cite(provs, instrument="Companies Act, 2013"):
    """Map every provision to its full citation, the way p04_structure does."""
    by_seq = {p.seq: p for p in provs}
    out = {}
    for leaf in provs:
        chain, cur = [], leaf
        while cur is not None:
            chain.append(cur)
            cur = by_seq.get(cur.parent_seq) if cur.parent_seq is not None else None
        chain.reverse()
        out.setdefault(build_citation(leaf, chain, instrument), []).append(leaf)
    return out


def test_act_marginal_note_is_split_from_its_first_subsection():
    """'62. Further issue of share capital.-(1) Where ...' must yield s.62(1).

    Without the split the '(1)' is swallowed into the heading and the clauses
    attach to the section, giving s.62(a) where a rule needs s.62(1)(a).
    """
    provs = parse_provisions(_pages(
        "62. Further issue of share capital.-(1) Where at any time a company\n"
        "(a) to persons who are holders of equity shares of the company\n"), "ACT")
    types = [(p.provision_type, p.number) for p in provs]
    assert ("SECTION", "62") in types
    assert ("SUB_SECTION", "1") in types
    section = [p for p in provs if p.provision_type == "SECTION"][0]
    assert section.heading == "Further issue of share capital."
    assert "s.62(1)(a)" in " ".join(_cite(provs))


def test_act_marginal_note_split_allows_a_space_after_the_dash():
    """The Act prints both '.-(1)' and '.- (1)'; 240 of its sections use the space."""
    provs = parse_provisions(_pages(
        "179. Powers of Board.- (1) The Board of Directors shall exercise\n"), "ACT")
    assert ("SUB_SECTION", "1") in [(p.provision_type, p.number) for p in provs]


def test_mid_sentence_parenthetical_does_not_split_a_heading():
    """The separator is anchored on '.' or ':' before the dash, not any '(1)'."""
    provs = parse_provisions(_pages(
        "15. A company may, under sub-section (1) of section 12, alter its name\n"),
        "ACT")
    assert not any(p.provision_type == "SUB_SECTION" for p in provs)


def test_substituted_subsection_is_not_lost_to_body_text():
    """'1[(3) ...' carries an amendment marker; without it the sub-section vanished."""
    provs = parse_provisions(_pages(
        "179. Powers of Board.\n"
        "1[(3) The Board shall exercise the following powers\n"
        "36[(c)] to issue securities, including debentures\n"), "ACT")
    types = [(p.provision_type, p.number) for p in provs]
    assert ("SUB_SECTION", "3") in types
    assert ("CLAUSE", "c") in types


def test_numbered_explanation_is_a_provision():
    """'Explanation 1.-' and 'Explanation II:' are as common as the bare form."""
    for text in ("Explanation 1.-Nothing in clause (d) shall apply\n",
                 "Explanation II.-In respect of dealings between a company\n",
                 "Explanation.-For the purposes of this section\n"):
        provs = parse_provisions(_pages("179. Powers of Board.\n" + text), "ACT")
        assert any(p.provision_type == "EXPLANATION" for p in provs), text


def test_clause_c_after_clause_b_is_not_a_roman_subclause():
    """'c' is also roman 100, so (c) was nested under (b) as a sub-clause.

    That is why s.62(1)(c) and s.179(3)(c), both named in source_gaps.yaml,
    could not be cited at all.
    """
    provs = parse_provisions(_pages(
        "179. Powers of Board.- (3) The Board shall exercise the following powers\n"
        "(a) to make calls on shareholders\n"
        "(b) to authorise buy-back of securities under section 68\n"
        "(c) to issue securities, including debentures\n"
        "(d) to borrow monies\n"), "ACT")
    cites = _cite(provs)
    assert "Companies Act, 2013 s.179(3)(c)" in cites
    assert not any(p.provision_type == "SUB_CLAUSE" for p in provs)


def test_genuine_roman_subclause_still_nests():
    """A clause that opens its own (i)/(ii) list must keep nesting."""
    provs = parse_provisions(_pages(
        "62. Further issue of share capital.-(1) Such shares shall be offered-\n"
        "(a) to holders of equity shares subject to the following conditions:-\n"
        "(i) the offer shall be made by notice specifying the number of shares\n"
        "(ii) the offer shall be deemed to include a right to renounce\n"), "ACT")
    cites = _cite(provs)
    assert "Companies Act, 2013 s.62(1)(a)(i)" in cites
    assert "Companies Act, 2013 s.62(1)(a)(ii)" in cites


def test_arrangement_of_sections_front_matter_is_suppressed():
    """The Act's index repeats every section, colliding with the real one."""
    provs = parse_provisions(_pages(
        "ARRANGEMENT OF SECTIONS\n"
        "62. Further issue of share capital.\n"
        "63. Issue of bonus shares.\n"
        "ACT NO. 18 OF 2013\n"
        "62. Further issue of share capital.-(1) Where at any time a company\n"), "ACT")
    sections = [p for p in provs if p.provision_type == "SECTION"]
    assert [p.number for p in sections] == ["62"], "the index was not suppressed"


def test_front_matter_without_an_operative_start_is_left_alone():
    """Losing a whole document to a runaway span is worse than the ambiguity."""
    provs = parse_provisions(_pages(
        "ARRANGEMENT OF SECTIONS\n"
        "62. Further issue of share capital.\n"), "ACT")
    assert any(p.provision_type == "SECTION" for p in provs)


def test_table_of_contents_in_body_text_is_not_front_matter():
    """ICDR Schedule VI prescribes a prospectus's own table of contents; keying
    front-matter suppression on that phrase would suppress a third of ICDR."""
    provs = parse_provisions(_pages(
        "(2) Table of Contents: The table of contents shall appear immediately\n"
        "164. Pricing of frequently traded shares\n"), "REGULATIONS")
    assert any(p.provision_type == "REGULATION" and p.number == "164" for p in provs)


def test_chapter_and_part_both_survive_in_citation():
    """Part must not evict its own Chapter from the citation."""
    provs = parse_provisions(_pages(
        "CHAPTER V\nPART IV\n164. Pricing of frequently traded shares\n"), "REGULATIONS")
    by_seq = {p.seq: p for p in provs}
    leaf = [p for p in provs if p.provision_type == "REGULATION"][0]
    chain, cur = [], leaf
    while cur is not None:
        chain.append(cur)
        cur = by_seq.get(cur.parent_seq) if cur.parent_seq is not None else None
    chain.reverse()
    cite = build_citation(leaf, chain, "SEBI (ICDR) Regulations, 2018")
    assert "Chapter V" in cite and "Part IV" in cite and "reg.164" in cite


def test_inline_references_extracted():
    refs = extract_references("as per section 62(1)(a) read with regulation 164(1)")
    kinds = {(r["kind"], r["number"], r["sub"]) for r in refs}
    assert ("SECTION", "62", "(1)(a)") in kinds
    assert ("REGULATION", "164", "(1)") in kinds


# ------------------------------------------------- Python <-> SQL AST parity
AST_CASES = [
    ({"op": "eq", "field": "a", "value": 1}, True),
    ({"op": "eq", "field": "a"}, False),
    ({"op": "AND", "args": [{"op": "eq", "field": "a", "value": 1}]}, True),
    ({"op": "AND", "args": []}, False),
    ({"op": "OR", "args": [{"op": "exists", "field": "a"},
                           {"op": "NOT", "arg": {"op": "eq", "field": "b", "value": 2}}]}, True),
    ({"op": "NOT"}, False),
    ({"op": "in", "field": "a", "value": ["x"]}, True),
    ({"op": "in", "field": "a", "value": "x"}, False),
    ({"op": "REGEX", "field": "a", "value": "x"}, False),
    ({"op": "exists", "field": "a"}, True),
    ({"op": "AND", "args": [{"op": "bogus", "field": "a", "value": 1}]}, False),
    # Aggregates over a list of records.
    ({"op": "count_where", "field": "previous_issues",
      "where": {"op": "eq", "field": "issue_type", "value": "BONUS"},
      "op2": "lte", "value": 2}, True),
    ({"op": "any_where", "field": "previous_issues",
      "where": {"op": "eq", "field": "issue_type", "value": "BONUS"}}, True),
    # count_where without a comparison has nothing to compare the count to.
    ({"op": "count_where", "field": "x",
      "where": {"op": "eq", "field": "a", "value": 1}}, False),
    ({"op": "count_where", "field": "x",
      "where": {"op": "eq", "field": "a", "value": 1}, "op2": "bogus", "value": 1}, False),
    # A malformed inner test must invalidate the whole aggregate.
    ({"op": "any_where", "field": "x", "where": {"op": "eq", "field": "a"}}, False),
    ({"op": "any_where", "field": "x"}, False),
]


# ------------------------------------------------------------- aggregates
_HISTORY = {"previous_issues": [
    {"issue_type": "PRIVATE_PLACEMENT", "allotment_date": "2026-02-01"},
    {"issue_type": "PRIVATE_PLACEMENT", "allotment_date": "2026-05-01"},
    {"issue_type": "BONUS"},
]}


def test_count_where_counts_matching_records():
    ast = {"op": "count_where", "field": "previous_issues",
           "where": {"op": "eq", "field": "issue_type", "value": "PRIVATE_PLACEMENT"},
           "op2": "lte", "value": 2}
    out = C.evaluate_safe(ast, _HISTORY)
    assert out["status"] == "EVALUATED" and out["result"] is True
    assert out["trace"][0]["actual"] == 2


def test_any_where_is_true_when_one_record_matches():
    ast = {"op": "any_where", "field": "previous_issues",
           "where": {"op": "eq", "field": "issue_type", "value": "BONUS"}}
    assert C.evaluate_safe(ast, _HISTORY)["result"] is True


def test_incomplete_history_row_is_not_a_match_and_does_not_block():
    """One row missing the field must not make the whole rule indeterminate."""
    ast = {"op": "count_where", "field": "previous_issues",
           "where": {"op": "eq", "field": "allotment_date", "value": "2026-02-01"},
           "op2": "eq", "value": 1}
    out = C.evaluate_safe(ast, _HISTORY)
    assert out["status"] == "EVALUATED" and out["result"] is True


def test_absent_history_is_review_required_not_false():
    """An unsupplied list is unknown, not empty - the engine's core contract."""
    ast = {"op": "any_where", "field": "previous_issues",
           "where": {"op": "eq", "field": "issue_type", "value": "BONUS"}}
    out = C.evaluate_safe(ast, {})
    assert out["status"] == "REVIEW_REQUIRED"
    assert out["missing_field"] == "previous_issues"


def test_empty_history_evaluates_rather_than_blocking():
    """An explicitly empty list IS known: nothing matches, so the answer is false."""
    ast = {"op": "any_where", "field": "previous_issues",
           "where": {"op": "eq", "field": "issue_type", "value": "BONUS"}}
    out = C.evaluate_safe(ast, {"previous_issues": []})
    assert out["status"] == "EVALUATED" and out["result"] is False


def _psql_available():
    try:
        return subprocess.run(["psql", "-d", "legal_rules_dev", "-c", "SELECT 1"],
                              capture_output=True, timeout=10).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


@pytest.mark.skipif(not _psql_available(), reason="legal_rules_dev not reachable")
def test_python_and_sql_validators_agree():
    """One AST contract, two implementations - they must never diverge."""
    mismatches = []
    for ast, expected in AST_CASES:
        assert C.validate(ast) is expected, f"python validator wrong for {ast}"
        res = subprocess.run(
            ["psql", "-tAX", "-d", "legal_rules_dev", "-c",
             f"SELECT legal.validate_condition_ast('{json.dumps(ast)}'::jsonb)"],
            capture_output=True, text=True, timeout=15)
        sql_says = res.stdout.strip() == "t"
        if sql_says != expected:
            mismatches.append((ast, expected, sql_says))
    assert not mismatches, f"SQL/Python validator disagreement: {mismatches}"


# ------------------------------------------------------------ supersession
def test_family_key_ignores_acronym_gloss():
    """SEBI prints the same circular with and without its acronym."""
    assert (S.family_key("Master Circular for Credit Rating Agencies (CRAs)")
            == S.family_key("Master Circular for Credit Rating Agencies"))
    assert (S.family_key("Master Circular for Debenture Trustees (DTs)")
            == S.family_key("Master Circular for Debenture Trustees"))


def test_family_key_ignores_updated_marker_and_connective():
    assert (S.family_key("Master Circular for Real Estate Investment Trusts (REITs) (Updated)")
            == S.family_key("Master Circular for Real Estate Investment Trusts (REITs)"))
    # "for", "on" and a bare dash are all used to join the label to the subject.
    assert (S.family_key("Master Circular-Mutual Funds")
            == S.family_key("Master Circular for Mutual Funds"))
    assert (S.family_key("Master Circular on Electronic Gold Receipts (EGR)")
            == S.family_key("Master Circular for Electronic Gold Receipts (EGRs)"))


def test_family_key_ignores_singular_plural_drift():
    assert (S.family_key("Master Circular for Stock Exchange and Clearing Corporation")
            == S.family_key("Master Circular for Stock Exchanges and Clearing Corporations"))


def test_family_key_strips_markup_spilled_into_a_listing_title():
    """One 2008 listing row carries its own anchor markup in the title."""
    spilled = ("PDF\" class='points'>Master Circular on Anti Money Laundering and "
               "Combating Financing of Terrorism (AML and CFT) Standards-PDF")
    assert S.clean_title(spilled).startswith("Master Circular on Anti Money Laundering")
    assert '>' not in S.clean_title(spilled)
    assert S.family_key(spilled) == S.family_key(S.clean_title(spilled))


def test_family_key_keeps_genuinely_different_circulars_apart():
    """Under-merging costs redundant extraction; over-merging loses a source."""
    assert (S.family_key("Master Circular for Mutual Funds")
            != S.family_key("Master Circular for Stock Brokers"))
    # A long parenthetical is doing real work and must not be stripped as a gloss.
    assert (S.family_key("Master Circular on Scheme of Arrangement")
            != S.family_key("Master Circular on (i) Scheme of Arrangement by Listed "
                            "Entities and (ii) Relaxation under Sub-rule (7) of rule 19"))


def test_newest_edition_is_in_force_and_others_name_it():
    recs = [
        {"document_key": "a", "title": "Master Circular for Depositories", "date": "Apr 06, 2010"},
        {"document_key": "b", "title": "Master Circular for Depositories", "date": "Dec 03, 2024"},
        {"document_key": "c", "title": "Master Circular for Depositories", "date": "Oct 06, 2023"},
    ]
    out = S.classify(recs)
    assert out["b"]["status"] == "ACTIVE"
    assert out["b"]["superseded_by"] is None
    for key in ("a", "c"):
        assert out[key]["status"] == "SUPERSEDED"
        assert out[key]["superseded_by"] == "b", "must name the edition that replaced it"
        assert out[key]["supersession_basis"] == "INFERRED_TITLE_DATE"


def test_supersession_is_never_reported_as_a_declaration():
    """consolidation_status is a reviewer's word; this heuristic must not borrow it."""
    out = S.classify([
        {"document_key": "old", "title": "Master Circular for Custodians", "date": "Apr 27, 2023"},
        {"document_key": "new", "title": "Master Circular for Custodians", "date": "May 10, 2024"},
    ])
    assert out["old"]["supersession_basis"] == "INFERRED_TITLE_DATE"
    assert "consolidation_status" not in out["old"]


def test_undated_edition_is_left_in_force_rather_than_ranked_last():
    """Sorting an unreadable date last would supersede a document on no evidence."""
    out = S.classify([
        {"document_key": "dated", "title": "Master Circular for Custodians", "date": "May 10, 2024"},
        {"document_key": "undated", "title": "Master Circular for Custodians", "date": "n/a"},
    ])
    assert out["undated"]["status"] == "ACTIVE"
    assert out["undated"]["publication_date"] is None


def test_extraction_gate_defers_superseded_and_out_of_scope():
    assert S.is_extractable({"scope": "COMPANY", "status": "ACTIVE"})
    assert not S.is_extractable({"scope": "COMPANY", "status": "SUPERSEDED"})
    assert not S.is_extractable({"scope": "REIT_INVIT", "status": "ACTIVE"})


def test_every_deferral_states_a_reason():
    """A document dropped from extraction must say why, never disappear silently."""
    assert S.deferral_reason({"scope": "COMPANY", "status": "ACTIVE"}) is None
    assert "REIT_INVIT" in S.deferral_reason({"scope": "REIT_INVIT", "status": "ACTIVE"})
    reason = S.deferral_reason({"scope": "COMPANY", "status": "SUPERSEDED",
                                "superseded_by": "x", "supersession_basis": "INFERRED_TITLE_DATE"})
    assert "SUPERSEDED" in reason and "x" in reason


def test_corpus_has_no_duplicate_hashes():
    """A second copy of the same bytes would upsert over the row rules cite.

    legal_sources.file_hash is UNIQUE and p06 upserts on it, so two inventory
    records sharing a hash silently collapse into one row whose title and path
    depend on load order.
    """
    inv_path = ROOT / "data" / "inventory" / "inventory.json"
    if not inv_path.exists():
        pytest.skip("inventory not built")
    inv = json.loads(inv_path.read_text())
    assert inv["duplicates_exact"] == {}, (
        f"duplicate file hashes in corpus: {inv['duplicates_exact']}")


def test_every_superseded_document_names_its_successor():
    inv_path = ROOT / "data" / "inventory" / "inventory.json"
    if not inv_path.exists():
        pytest.skip("inventory not built")
    inv = json.loads(inv_path.read_text())
    by_id = {d["document_id"]: d for d in inv["documents"]}
    for d in inv["documents"]:
        if d.get("status") == "SUPERSEDED":
            succ = d.get("superseded_by")
            assert succ, f"{d['file_name']} is SUPERSEDED but names no successor"
            assert succ in by_id, f"{d['file_name']} names a successor not in the corpus"
            assert by_id[succ]["status"] == "ACTIVE", (
                f"{d['file_name']} points at an edition that is not in force")


def test_plural_annexures_is_not_annexure_s():
    """Regression: "ANNEXURES" parsed as Annexure "S".

    [A-Z] consumed the final S and \\b was satisfied by the end of the word, so
    a contents page headed ANNEXURES opened a provision with no heading and no
    body, and everything after it was reparented under that phantom.
    """
    from lib.citations import RE_ANNEXURE
    assert RE_ANNEXURE.match("ANNEXURES") is None
    assert RE_ANNEXURE.match("ANNEXURES TO THE MASTER CIRCULAR") is None
    # ...while genuine annexure headings still parse.
    assert RE_ANNEXURE.match("ANNEXURE II").group("num") == "II"
    assert RE_ANNEXURE.match("ANNEXURE-I").group("num") == "I"
    assert RE_ANNEXURE.match("ANNEXURE A").group("num") == "A"
    assert RE_ANNEXURE.match("ANNEXURE") is not None
