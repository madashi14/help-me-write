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


def _skip_reason(p, last, value) -> str | None:
    """Why a page is not evaluated by a per-page check, or None if it is."""
    if p.number == 1:
        return "title page"
    if not p.is_full:
        if not p.body_lines:
            return "no body text"
        if p.number == last:
            return "last page"
        return "not a full page: the text ends early or a figure or table interrupts it"
    if value(p) is None:
        return "no full-width lines"
    return None


def _per_page(rule, pages, rng, value, unit) -> Check:
    last = max((p.number for p in pages), default=0)
    skipped = {}
    for p in pages:
        reason = _skip_reason(p, last, value)
        if reason:
            skipped.setdefault(reason, []).append(p.number)
    note = ("; not evaluated: " + "; ".join(f"{_page_list(numbers)} ({reason})"
                                            for reason, numbers in skipped.items())
            if skipped else "")
    evaluated = [p for p in pages if _skip_reason(p, last, value) is None]
    if not evaluated:
        return Check(rule, False, f"could not evaluate any page ({_allowed(rng)}){note}", [])
    bad = [p for p in evaluated if not _in_range(value(p), rng)]
    if bad:
        parts = [f"page {p.number}: {_num(value(p))} {unit}" for p in bad[:MAX_LISTED_PAGES]]
        if len(bad) > MAX_LISTED_PAGES:
            parts.append(f"and {len(bad) - MAX_LISTED_PAGES} more pages")
        return Check(rule, False, "; ".join(parts) + f" ({_allowed(rng)}){note}",
                     [p.number for p in bad])
    values = [value(p) for p in evaluated]
    lo, hi = min(values), max(values)
    amount = _num(lo) if lo == hi else f"{_num(lo)}–{_num(hi)}"
    evaluated_pages = _page_list(p.number for p in evaluated)
    return Check(rule, True, f"{amount} {unit} on full pages {evaluated_pages} "
                             f"({_allowed(rng)}){note}", [])


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
                     f"no page number on pages {_page_list(missing)} (looked for a number alone, "
                     "or 'pag./pagina/page N', in the top or bottom 7% of the page)", missing)
    return Check("page_numbers", True,
                 f"page number found on pages {_page_list(p.number for p in evaluated)}", [])


def _heading_matches(title: str, names) -> bool:
    key = heading_key(title)
    return any(re.match(re.escape(normalize_text(n)) + r"(?!\w)", key) for n in names)


def _section_checks(spans, section_rules) -> list[Check]:
    """Sections without headings (title page, body) are identified by position: not checked.

    spans is None when the source has no readable headings (.tex, .pdf): every required
    section with headings is then reported as not determined (ok=False), to check by hand.
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
                                lambda p: p.body_lines, "body lines"))
    if rules.chars_per_line is not None:
        checks.append(_per_page("chars_per_line", m_pages, rules.chars_per_line,
                                lambda p: p.chars_per_full_line, "chars per full line"))
    if rules.page_numbers:
        checks.append(_page_numbers(m_pages))
    checks.extend(_section_checks(sections, rules.sections))
    return checks
