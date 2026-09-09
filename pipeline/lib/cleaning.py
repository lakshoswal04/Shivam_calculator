"""Text cleaning that repairs extraction artefacts without altering legal wording.

Hard rule (brief §4): raw text is never mutated. These functions return a NEW
string; callers persist raw_text and cleaned_text side by side.
"""
import re
from collections import Counter
from typing import List

LIGATURES = {
    "ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl",
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", " ": " ", "​": "",
}

# A hyphen at end-of-line followed by a lowercase continuation = split word.
_HYPHEN_BREAK = re.compile(r"(\w)-\s*\n\s*([a-z])")
_MULTI_BLANK = re.compile(r"\n{3,}")
_TRAIL_WS = re.compile(r"[ \t]+\n")
_MULTI_SPACE = re.compile(r"[ \t]{2,}")


def normalise_chars(text: str) -> str:
    for bad, good in LIGATURES.items():
        text = text.replace(bad, good)
    return text


def repair_hyphenation(text: str) -> str:
    return _HYPHEN_BREAK.sub(r"\1\2", text)


def find_running_headers(pages: List[str], min_ratio: float = 0.5) -> set:
    """Lines repeating on >= min_ratio of pages are running headers/footers.

    Requires >= 4 pages; below that, repetition is not evidence of boilerplate.
    Numeric-only lines (page numbers) are always treated as boilerplate.
    """
    if len(pages) < 4:
        return set()
    counts = Counter()
    for page in pages:
        lines = [ln.strip() for ln in page.splitlines() if ln.strip()]
        for ln in set(lines[:3] + lines[-3:]):
            counts[ln] += 1
    threshold = max(2, int(len(pages) * min_ratio))
    return {ln for ln, n in counts.items() if n >= threshold and len(ln) < 120}


def strip_boilerplate(text: str, boilerplate: set) -> str:
    if not boilerplate:
        return text
    out = []
    for ln in text.splitlines():
        s = ln.strip()
        if s in boilerplate:
            continue
        if s.isdigit() and len(s) <= 4:  # bare page number
            continue
        out.append(ln)
    return "\n".join(out)


def clean_page(raw: str, boilerplate: set = frozenset()) -> str:
    t = normalise_chars(raw)
    t = repair_hyphenation(t)
    stripped = strip_boilerplate(t, boilerplate)
    # Cleaning removes noise; it must never remove the page. A short page whose
    # every line also appears elsewhere (a repeated signature block) would
    # otherwise be reduced to nothing, silently losing content that extraction
    # did capture.
    if not stripped.strip() and t.strip():
        stripped = t
    t = _TRAIL_WS.sub("\n", stripped)
    t = _MULTI_SPACE.sub(" ", t)
    t = _MULTI_BLANK.sub("\n\n", t)
    return t.strip()
