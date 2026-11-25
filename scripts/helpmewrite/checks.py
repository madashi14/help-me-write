"""Guideline checks on measured pages: one Check per rule, with details an agent can act on.

The pages come from measure.measure_pdf and the sections from measure.section_spans.
"""
import re
from collections import Counter
from dataclasses import dataclass

from .fonts import normalize_font

FONT_SHARE = 0.95
FONT_SIZE_TOLERANCE_PT = 0.5
MAX_LISTED_PAGES = 5
MIN_FULL_LINES = 5  # full lines of prose a page needs for chars_per_full_line (measure.py)

_NUMBERING = re.compile(
    r"^(?:(?:capitolo|chapter)\s+)?(?:\d+(?:\.\d+)*\.?|\d+\)|[ivxlc]+[.)])\s*[-–—:]?\s+")


@dataclass
class Check:
    rule: str
    ok: bool
    detail: str
    pages: list[int]


# --- heading text ------------------------------------------------------------------------

def normalize_text(text: str) -> str:
    return " ".join(text.split()).casefold()


def heading_key(text: str) -> str:
    """Normalized heading text without leading numbering ("1.2 ", "Capitolo 3 - ", "IV. ")."""
    return _NUMBERING.sub("", normalize_text(text), count=1)


# --- rules -------------------------------------------------------------------------------

def _num(value) -> str:
    return f"{round(value, 1):g}"


def _allowed(rng) -> str:
    if rng.min is not None and rng.max is not None:
        return f"allowed {_num(rng.min)}–{_num(rng.max)}"
    if rng.min is not None:
        return f"minimum {_num(rng.min)}"
    return f"maximum {_num(rng.max)}"


def _in_range(value, rng) -> bool:
    return (rng.min is None or value >= rng.min) and (rng.max is None or value <= rng.max)


def _page_list(numbers) -> str:
    """[2, 3, 4, 7] -> '2–4, 7'."""
    runs = []
    for n in sorted(numbers):
        if runs and n == runs[-1][-1] + 1:
            runs[-1].append(n)
        else:
            runs.append([n])
    return ", ".join(str(r[0]) if len(r) == 1 else f"{r[0]}–{r[-1]}" for r in runs)


def _pages(n) -> str:
    return f"{n} page{'s' if n != 1 else ''}"


def _lines_skip_reason(p, last) -> str | None:
    """Why lines_per_page does not evaluate a page, or None if it does (a full page)."""
    if p.number == 1:
        return "title page"
    if not p.body_lines:
        return "no body text"
    if not p.is_full or p.line_slots is None:
        if p.number == last:
            return "last page"
        return ("not a full page: the text starts late or ends early, or a figure or table "
                "without a caption leaves some of its lines empty")
    return None


def _chars_skip_reason(p, last) -> str | None:
    """Why chars_per_line does not evaluate a page, or None if it does."""
    if p.number == 1:
        return "title page"
    if not p.body_lines:
        return "no body text"
    if p.chars_per_full_line is None:
        return (f"fewer than {MIN_FULL_LINES} full-width lines of prose (a table of contents, "
                "a table or a list)")
    return None


def _per_page(rule, pages, rng, value, unit, skip_reason, scope, how="") -> Check:
    """A range check of value(p) on the pages skip_reason does not skip (scope names them);
    how, if given, says how the value is counted."""
    last = max((p.number for p in pages), default=0)
    skipped = {}
    for p in pages:
        reason = skip_reason(p, last)
        if reason:
            skipped.setdefault(reason, []).append(p.number)
    note = ("; not evaluated: " + "; ".join(f"{_page_list(numbers)} ({reason})"
                                            for reason, numbers in skipped.items())
            if skipped else "")
    allowed = _allowed(rng) + (f"; {how}" if how else "")
    evaluated = [p for p in pages if skip_reason(p, last) is None]
    if not evaluated:
        return Check(rule, False, f"could not evaluate any page ({allowed}){note}", [])
    bad = [p for p in evaluated if not _in_range(value(p), rng)]
    if bad:
        parts = [f"page {p.number}: {_num(value(p))} {unit}" for p in bad[:MAX_LISTED_PAGES]]
        if len(bad) > MAX_LISTED_PAGES:
            parts.append(f"and {len(bad) - MAX_LISTED_PAGES} more pages")
        return Check(rule, False, "; ".join(parts) + f" ({allowed}){note}",
                     [p.number for p in bad])
    values = [value(p) for p in evaluated]
    lo, hi = min(values), max(values)
    amount = _num(lo) if lo == hi else f"{_num(lo)}–{_num(hi)}"
    evaluated_pages = _page_list(p.number for p in evaluated)
    return Check(rule, True, f"{amount} {unit} on {scope} {evaluated_pages} ({allowed}){note}", [])


def _allowed_share(font_chars, allowed) -> float:
    chars = sum(font_chars.values())
    good = sum(n for name, n in font_chars.items() if normalize_font(name) in allowed)
    return good / chars if chars else 1.0


def _font_family(pages, fonts) -> Check:
    total = sum((Counter(p.font_chars) for p in pages), Counter())
    if not total:
        return Check("font_family", False, "no body text found in the PDF", [])
    allowed = {normalize_font(f) for f in fonts} - {None}
    share = _allowed_share(total, allowed)
    chars = sum(total.values())
    used = ", ".join(f"{name} {n / chars:.0%}" for name, n in total.most_common(4))
    detail = (f"{share:.0%} of body text in allowed fonts (required {FONT_SHARE:.0%}); "
              f"fonts in the PDF: {used}; allowed: {', '.join(fonts)}")
    if share >= FONT_SHARE:
        return Check("font_family", True, detail, [])
    return Check("font_family", False, detail, [
        p.number for p in pages if _allowed_share(p.font_chars, allowed) < FONT_SHARE])


def _font_size(pages, target) -> Check:
    weights = Counter()
    for p in pages:
        if p.body_size_pt is not None:
            weights[p.body_size_pt] += sum(p.font_chars.values())
    if not weights:
        return Check("font_size", False, "no body text found in the PDF", [])
    size = weights.most_common(1)[0][0]
    ok = abs(size - target) <= FONT_SIZE_TOLERANCE_PT
    return Check("font_size", ok, f"body text {_num(size)} pt (required {_num(target)} pt)", [])


def _page_numbers(pages) -> Check:
    evaluated = [p for p in pages if p.number != 1]
    if not evaluated:
        return Check("page_numbers", True, "not evaluated: the document has only page 1", [])
    missing = [p.number for p in evaluated if not p.has_page_number]
    if missing:
        return Check("page_numbers", False,
                     f"no page number on pages {_page_list(missing)}: looked for a number alone, "
                     "or 'pag./pagina/page N', in the header or footer (the lines above the text "
                     "or below it)", missing)
    return Check("page_numbers", True,
                 f"page number found on pages {_page_list(p.number for p in evaluated)}", [])


def _heading_matches(title: str, names) -> bool:
    key = heading_key(title)
    return any(re.match(re.escape(normalize_text(n)) + r"(?!\w)", key) for n in names)


_UNSTYLED_EXTRA_WORDS = 4


def _unstyled_heading(pages, names):
    """(page number, line) of a line of the PDF that is one of the heading names, optionally
    numbered ("1. Introduzione") and followed by a few words ("Conclusioni e sviluppi
    futuri"), but not a table-of-contents entry ("Introduzione 3") nor the end of a sentence.
    Pages after the first come first, as in measure._locate."""
    wanted = [normalize_text(n) for n in names]
    for p in sorted(pages, key=lambda p: (p.number == 1, p.number)):
        for line in p.text.splitlines():
            key = heading_key(line)
            for name in wanted:
                extra = len(key.split()) - len(name.split())
                if key == name or (key.startswith(name + " ") and extra <= _UNSTYLED_EXTRA_WORDS
                                   and not re.search(r"[\d.,;:]$", key)):
                    return p.number, " ".join(line.split())
    return None


def _section_checks(spans, section_rules, pages=()) -> list[Check]:
    """Sections without headings (title page, body) are identified by position: not checked.

    spans is None when the source has no readable headings (.tex, .pdf): every required
    section with headings is then reported as not determined (ok=False), to check by hand.
    A heading typed as plain (bold) text is found by a line of the PDF that is the heading:
    present, "not styled as a heading", and its length cannot be determined.
    """
    checks = []
    for rule in section_rules:
        if not rule.headings:
            continue
        rid = f"section:{rule.name}"
        names = " or ".join(f"'{n}'" for n in rule.headings)
        if spans is None:
            if rule.required:
                checks.append(Check(f"{rid}:present", False,
                                    "cannot determine sections: headings are read only from .docx "
                                    f"documents; check by hand for a heading {names}", []))
            continue
        span = next((s for s in spans if _heading_matches(s.title, rule.headings)), None)
        unstyled = _unstyled_heading(pages, rule.headings) if span is None else None
        if unstyled is not None:
            number, line = unstyled
            checks.append(Check(f"{rid}:present", True,
                                f"'{line}' found on page {number}, but not styled as a heading "
                                "(apply a Heading style so that it is in the table of contents)",
                                [number]))
            if rule.pages is not None:
                checks.append(Check(f"{rid}:pages", False,
                                    f"cannot determine the length of '{line}': it is not styled "
                                    f"as a heading ({_allowed(rule.pages)} pages)", [number]))
            continue
        if span is None:
            kind = "required" if rule.required else "optional"
            checks.append(Check(f"{rid}:present", not rule.required,
                                f"no heading {names} among the document's headings ({kind})",
                                []))
            continue
        checks.append(Check(f"{rid}:present", True,
                            f"heading '{span.title}' on page {span.start_page}", [span.start_page]))
        if rule.pages is not None:
            n = span.end_page - span.start_page + 1
            checks.append(Check(
                f"{rid}:pages", _in_range(n, rule.pages),
                f"'{span.title}': {_pages(n)} "
                f"(pages {span.start_page}–{span.end_page}; {_allowed(rule.pages)})",
                list(range(span.start_page, span.end_page + 1))))
    return checks


def check_rules(m_pages, sections, rules) -> list[Check]:
    """One Check per rule present in the guidelines; sections=None means headings unknown."""
    checks = []
    if rules.pages is not None:
        n = len(m_pages)
        checks.append(Check("pages", _in_range(n, rules.pages),
                            f"{_pages(n)} ({_allowed(rules.pages)})", []))
    if rules.fonts:
        checks.append(_font_family(m_pages, rules.fonts))
    if rules.font_size_pt is not None:
        checks.append(_font_size(m_pages, rules.font_size_pt))
    if rules.lines_per_page is not None:
        checks.append(_per_page("lines_per_page", m_pages, rules.lines_per_page,
                                lambda p: p.line_slots, "body lines", _lines_skip_reason,
                                "full pages", "a heading or caption counts for the lines it takes"))
    if rules.chars_per_line is not None:
        checks.append(_per_page("chars_per_line", m_pages, rules.chars_per_line,
                                lambda p: p.chars_per_full_line, "chars per full line",
                                _chars_skip_reason, "pages"))
    if rules.page_numbers:
        checks.append(_page_numbers(m_pages))
    checks.extend(_section_checks(sections, rules.sections, m_pages))
    return checks
