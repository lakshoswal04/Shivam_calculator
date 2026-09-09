"""Parse the legal hierarchy out of extracted text (brief §5).

Produces a tree of provisions, each anchored to document + page + character
offset, so every future rule can cite an exact location.

Deliberately conservative: it only emits a provision when the text carries an
unambiguous structural marker. Prose that merely mentions "section 62" is not
treated as a heading. Anything doubtful is left as body text of its parent
rather than invented as a new node (brief §29).
"""
import re
from dataclasses import dataclass, field
from typing import List, Optional

ROMAN = r"(?:[IVXLC]+)"

# --- Structural markers -----------------------------------------------------
# Top-level numbered unit at start of a line: "62. Further issue..." / "13. Issue..."
# SEBI/MCA gazette text carries amendment footnote markers inline, e.g.
#   "166. 335[(1)] The price determined ..."   "305[90 trading days]"
# The marker must not hide the provision, and it is itself evidence that the
# text was substituted by a later amendment, so it is captured rather than
# stripped.
RE_AMENDMENT_MARKER = re.compile(r"(?<!\d)(\d{1,3})\[")
_MARKER = r"(?:\d{1,3}\[)?"
RE_NUMBERED_UNIT = re.compile(
    r"^\s{0,6}(?P<num>\d{1,3}[A-Z]{0,2})\s*\.\s+(?P<head>" + _MARKER + r"[A-Za-z(\[—-].{0,200}?)\s*$"
)
# An inline sub-unit opening a numbered unit: "(1) ..." or "335[(1)] ..."
RE_INLINE_SUBUNIT = re.compile(r"^" + _MARKER + r"\((?P<num>\d{1,2})\)\]?\s*(?P<rest>.*)$")
# Structural headings are set in capitals in the gazette; a title-case
# "Schedule VI, as applicable" is a cross-reference inside a sentence that has
# wrapped onto its own line. Matching case-insensitively made every such
# reference open a new Schedule and mis-scoped every provision after it, so
# these patterns are deliberately case-sensitive.
RE_CHAPTER = re.compile(r"^\s*CHAPTER[\s–-]+(?P<num>" + ROMAN + r")\b\.?\s*(?P<head>.*)$")
RE_PART = re.compile(r"^\s*PART[\s–-]+(?P<num>" + ROMAN + r")\b\.?\s*(?P<head>.*)$")
RE_SCHEDULE = re.compile(r"^\s*(?:THE\s+)?SCHEDULE[\s–-]*(?P<num>" + ROMAN + r"|\d+)?\b\.?\s*(?P<head>.*)$")
RE_ANNEXURE = re.compile(r"^\s*ANNEXURE[\s–-]*(?P<num>" + ROMAN + r"|\d+|[A-Z])?\b\.?\s*(?P<head>.*)$")
RE_SUBUNIT = re.compile(r"^\s{0,10}\((?P<num>\d{1,2})\)\s+(?P<head>\S.*)$")
RE_CLAUSE = re.compile(r"^\s{0,14}\((?P<num>[a-z]{1,2})\)\s+(?P<head>\S.*)$")
RE_SUBCLAUSE = re.compile(r"^\s{0,18}\((?P<num>" + ROMAN.lower() + r")\)\s+(?P<head>\S.*)$")
RE_PROVISO = re.compile(r"^\s*(?P<head>Provided\s+(?:further\s+|also\s+)?that\b.*)$", re.I)
RE_EXPLANATION = re.compile(r"^\s*(?P<head>Explanation\s*[—.\-:].*)$", re.I)

# --- Inline citation references (for cross-linking, not structure) ----------
RE_REF_SECTION = re.compile(r"\bsection\s+(\d{1,3}[A-Z]{0,2})((?:\s*\([0-9a-zA-Z]{1,3}\))*)", re.I)
RE_REF_REGULATION = re.compile(r"\bregulation\s+(\d{1,3}[A-Z]{0,2})((?:\s*\([0-9a-zA-Z]{1,3}\))*)", re.I)
RE_REF_RULE = re.compile(r"\brule\s+(\d{1,3}[A-Z]{0,2})((?:\s*\([0-9a-zA-Z]{1,3}\))*)", re.I)

# Instrument kind -> label used for its top-level numbered unit
TOP_UNIT = {
    "ACT": "SECTION",
    "RULES": "RULE",
    "REGULATIONS": "REGULATION",
    "CIRCULAR": "PARAGRAPH",
    "CHECKLIST": "ITEM",
    "FAQ": "QUESTION",
    "UNKNOWN": "PARAGRAPH",
}
# Depth drives stack nesting: pushing a node pops everything at or below its
# depth. Chapter and Part must NOT share a depth, or a Part evicts its own
# Chapter from the stack and the chapter is lost from the citation.
DEPTH = {
    "CHAPTER": 0, "SCHEDULE": 0, "ANNEXURE": 0,
    "PART": 1,
    "SECTION": 2, "RULE": 2, "REGULATION": 2, "PARAGRAPH": 2, "ITEM": 2, "QUESTION": 2,
    "SUB_SECTION": 3, "SUB_RULE": 3, "SUB_REGULATION": 3,
    "CLAUSE": 4, "SUB_CLAUSE": 5, "PROVISO": 6, "EXPLANATION": 6,
}
TOP_UNIT_DEPTH = 2  # depth of Section/Rule/Regulation, the operative unit
SUB_OF = {"SECTION": "SUB_SECTION", "RULE": "SUB_RULE", "REGULATION": "SUB_REGULATION",
          "PARAGRAPH": "SUB_SECTION", "ITEM": "SUB_SECTION", "QUESTION": "SUB_SECTION"}


@dataclass
class Provision:
    seq: int
    provision_type: str
    number: str
    heading: str
    depth: int
    page_from: int
    page_to: int
    char_start: int
    parent_seq: Optional[int] = None
    lines: List[str] = field(default_factory=list)
    inline_split: bool = False

    @property
    def amendment_markers(self):
        """Footnote numbers marking text substituted by later amendments."""
        return sorted(set(RE_AMENDMENT_MARKER.findall(f"{self.heading}\n{self.body}")))

    @property
    def body(self) -> str:
        return "\n".join(self.lines).strip()


def _iter_lines(pages):
    """Yield (page_no, char_offset_within_page, line) across the document."""
    for p in pages:
        offset = 0
        for line in p["cleaned_text"].splitlines():
            yield p["page_no"], offset, line
            offset += len(line) + 1


def parse_provisions(pages, instrument_kind="UNKNOWN"):
    """Return a flat list of Provision objects with parent links."""
    top_label = TOP_UNIT.get(instrument_kind, "PARAGRAPH")
    sub_label = SUB_OF.get(top_label, "SUB_SECTION")
    out: List[Provision] = []
    stack: List[Provision] = []
    seq = 0

    def push(ptype, num, head, page, off):
        nonlocal seq
        depth = DEPTH[ptype]
        while stack and stack[-1].depth >= depth:
            stack.pop()
        parent = stack[-1].seq if stack else None
        prov = Provision(seq=seq, provision_type=ptype, number=num, heading=head.strip(),
                         depth=depth, page_from=page, page_to=page, char_start=off,
                         parent_seq=parent)
        out.append(prov)
        stack.append(prov)
        seq += 1
        return prov

    for page_no, off, line in _iter_lines(pages):
        s = line.strip()
        if not s:
            if stack:
                stack[-1].lines.append("")
            continue

        m = RE_CHAPTER.match(s)
        if m and len(s) < 120:
            push("CHAPTER", m.group("num"), m.group("head"), page_no, off); continue
        m = RE_SCHEDULE.match(s)
        if m and len(s) < 120 and s.startswith(("SCHEDULE", "THE SCHEDULE")):
            push("SCHEDULE", m.group("num") or "", m.group("head"), page_no, off); continue
        m = RE_ANNEXURE.match(s)
        if m and len(s) < 120 and s.startswith("ANNEXURE"):
            push("ANNEXURE", m.group("num") or "", m.group("head"), page_no, off); continue
        m = RE_PART.match(s)
        if m and len(s) < 120:
            push("PART", m.group("num"), m.group("head"), page_no, off); continue

        m = RE_NUMBERED_UNIT.match(line)
        if m:
            head = m.group("head")
            # Inside a Schedule or Annexure a numbered item is a paragraph, not
            # a regulation. Typing it as a regulation both mislabels it and
            # collides with the real regulation of the same number.
            in_annex = any(n.provision_type in ("SCHEDULE", "ANNEXURE") for n in stack)
            label_here = "PARAGRAPH" if in_annex else top_label
            sub_here = "SUB_SECTION" if in_annex else sub_label
            # "164. (1) If the equity shares ..." carries both the regulation and
            # its first sub-regulation on one line. Without splitting, reg.164(1)
            # cannot be cited apart from reg.164, which a rule engine needs.
            inline = RE_INLINE_SUBUNIT.match(head)
            unit = push(label_here, m.group("num"), "" if inline else head, page_no, off)
            if inline:
                sub = push(sub_here, inline.group("num"), inline.group("rest")[:160], page_no, off)
                sub.inline_split = True
            continue

        m = RE_EXPLANATION.match(s)
        if m and stack:
            push("EXPLANATION", "", m.group("head")[:120], page_no, off); continue
        m = RE_PROVISO.match(s)
        if m and stack:
            push("PROVISO", "", m.group("head")[:120], page_no, off); continue

        m = RE_SUBUNIT.match(line)
        if m and stack:
            push(sub_label, m.group("num"), m.group("head")[:160], page_no, off); continue
        m = RE_SUBCLAUSE.match(line)
        if m and stack and stack[-1].depth >= DEPTH["CLAUSE"]:
            push("SUB_CLAUSE", m.group("num"), m.group("head")[:160], page_no, off); continue
        m = RE_CLAUSE.match(line)
        if m and stack:
            push("CLAUSE", m.group("num"), m.group("head")[:160], page_no, off); continue

        if stack:
            stack[-1].lines.append(line)
            for node in stack:
                node.page_to = max(node.page_to, page_no)

    return out


def build_citation(prov, chain, instrument_label):
    """Canonical citation, e.g. 'Companies Act, 2013 s.62(1)(a)'."""
    prefix = {"SECTION": "s.", "RULE": "r.", "REGULATION": "reg.",
              "PARAGRAPH": "para ", "ITEM": "item ", "QUESTION": "Q"}
    # Every enclosing scope is kept, not just the innermost: ICDR has a Part
    # VIII inside more than one Chapter, so "Part VIII reg.40" is ambiguous
    # while "Chapter VI Part VIII reg.40" is not.
    parts, scopes = [], []
    for node in chain:
        t = node.provision_type
        if t in ("CHAPTER", "PART", "SCHEDULE", "ANNEXURE"):
            scopes.append(f"{t.title()} {node.number}".strip())
        elif t in prefix:
            parts.append(f"{prefix[t]}{node.number}")
        elif t in ("SUB_SECTION", "SUB_RULE", "SUB_REGULATION", "CLAUSE", "SUB_CLAUSE"):
            parts.append(f"({node.number})")
        elif t == "PROVISO":
            parts.append(" proviso")
        elif t == "EXPLANATION":
            parts.append(" Explanation")
    body = "".join(parts)
    bits = [instrument_label] + scopes
    if body:
        bits.append(body)
    return " ".join(b for b in bits if b).strip()


def extract_references(text):
    """Inline cross-references, for later conflict/linkage analysis."""
    refs = []
    for kind, rx in (("SECTION", RE_REF_SECTION), ("REGULATION", RE_REF_REGULATION), ("RULE", RE_REF_RULE)):
        for m in rx.finditer(text):
            refs.append({"kind": kind, "number": m.group(1),
                         "sub": (m.group(2) or "").replace(" ", ""), "raw": m.group(0)})
    return refs
