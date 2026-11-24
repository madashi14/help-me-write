"""Measure a rendered PDF against the guidelines.

Pages, font family and size, body lines per page, characters per line (spaces included),
page numbers and section lengths. Algorithm:
- words come from pdfplumber with font name and size; a line is a group of words whose
  top is within 2 pt; its text is the words joined by single spaces;
- the body size is the most frequent size, weighted by characters; body lines are within
  0.6 pt of it and outside the header/footer bands (top and bottom 7% of the page);
- a full line is at least 90% as wide as the widest body line of the document;
- a full page has body lines spanning at least 75% of the mean span over pages with text;
- lines and characters per line are checked on full pages only, never on page 1 (title
  page); page numbers are checked on every page but page 1.

Departures from the plan's algorithm (accepted by the controller, ruling R6):
1. the last page is never full: the text ends there, so a page filled 75-95% would
   otherwise fail lines_per_page;
2. a heading is located on a page with a line that is the whole title (numbering stripped)
   before falling back to "the page text contains the title": table-of-contents entries
   ("Introduzione 3") and mentions in the prose would otherwise win;
3. page 1 is searched too, as a fallback for whole-line matches only, so a draft without a
   title page still finds an introduction on page 1.
"""
import re
import shutil
import statistics
import sys
import tempfile
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from .fonts import normalize_font
from .render import RenderError, render_pdf

LINE_TOP_TOLERANCE_PT = 2.0
WORD_JOIN_GAP_PT = 0.5      # fragments of one word split by a font change mid-word
BAND = 0.07                 # header and footer bands: top and bottom 7% of the page
BODY_SIZE_TOLERANCE_PT = 0.6
FULL_LINE_RATIO = 0.90
FULL_PAGE_RATIO = 0.75
FONT_SHARE = 0.95
FONT_SIZE_TOLERANCE_PT = 0.5
MAX_LISTED_PAGES = 5

_PAGE_NUMBER = re.compile(r"^\W*\d+\W*$|^(pag\.?|pagina|page)\s*\d+", re.IGNORECASE)
_SUBSET_PREFIX = re.compile(r"^[A-Z]{6}\+")
_NUMBERING = re.compile(
    r"^(?:(?:capitolo|chapter)\s+)?(?:\d+(?:\.\d+)*\.?|\d+\)|[ivxlc]+[.)])\s*[-–—:]?\s+")


@dataclass
class PageStats:
    number: int
    body_lines: int
    chars_per_full_line: float | None   # median over the page's full body lines
    font_chars: dict[str, int]          # PDF font name -> characters in body lines
    body_size_pt: float | None          # body size of the document; None without body lines
    has_page_number: bool
    is_full: bool
    text: str                           # every line of the page, top to bottom


@dataclass
class SectionSpan:
    title: str
    level: int
    start_page: int
    end_page: int


@dataclass
class Check:
    rule: str
    ok: bool
    detail: str
    pages: list[int]


@dataclass
class Measurement:
    source: str
    pdf: str
    page_count: int
    pages: list[PageStats]
    sections: list[SectionSpan]
    checks: list[Check]


# --- PDF lines ---------------------------------------------------------------------------

@dataclass
class _Line:
    text: str
    top: float
    bottom: float
    x0: float
    x1: float
    sizes: Counter   # size -> characters
    fonts: Counter   # font name -> characters

    @property
    def size(self) -> float:
        return self.sizes.most_common(1)[0][0]

    @property
    def width(self) -> float:
        return self.x1 - self.x0


def _make_line(words) -> _Line:
    words = sorted(words, key=lambda w: w["x0"])
    text, sizes, fonts = "", Counter(), Counter()
    prev = None
    for w in words:
        if prev is not None:
            text += "" if w["x0"] - prev["x1"] < WORD_JOIN_GAP_PT else " "
        text += w["text"]
        sizes[round(w["size"], 1)] += len(w["text"])
        fonts[_SUBSET_PREFIX.sub("", w["fontname"])] += len(w["text"])
        prev = w
    return _Line(text, min(w["top"] for w in words), max(w["bottom"] for w in words),
                 words[0]["x0"], max(w["x1"] for w in words), sizes, fonts)


def _lines(words) -> list[_Line]:
    lines, current = [], []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if current and w["top"] - current[0]["top"] > LINE_TOP_TOLERANCE_PT:
            lines.append(_make_line(current))
            current = []
        current.append(w)
    if current:
        lines.append(_make_line(current))
    return lines


def _in_band(line: _Line, height: float) -> bool:
    middle = (line.top + line.bottom) / 2
    return middle < BAND * height or middle > (1 - BAND) * height


def measure_pdf(pdf, body_size_pt: float | None = None) -> list[PageStats]:
    import pdfplumber

    with pdfplumber.open(str(pdf)) as doc:
        raw = [(page.height, _lines(page.extract_words(extra_attrs=["fontname", "size"])))
               for page in doc.pages]

    if body_size_pt is None:
        sizes = sum((line.sizes for _, lines in raw for line in lines), Counter())
        body_size_pt = sizes.most_common(1)[0][0] if sizes else None

    def is_body(line, height):
        return (body_size_pt is not None and not _in_band(line, height)
                and abs(line.size - body_size_pt) <= BODY_SIZE_TOLERANCE_PT)

    body = [[line for line in lines if is_body(line, height)] for height, lines in raw]
    widest = max((line.width for lines in body for line in lines), default=0.0)
    spans = [lines[-1].bottom - lines[0].top for lines in body if lines]
    mean_span = statistics.mean(spans) if spans else 0.0

    pages = []
    for number, ((height, lines), body_lines) in enumerate(zip(raw, body), start=1):
        full = [len(line.text) for line in body_lines if line.width >= FULL_LINE_RATIO * widest]
        fonts = sum((line.fonts for line in body_lines), Counter())
        span = body_lines[-1].bottom - body_lines[0].top if body_lines else 0.0
        pages.append(PageStats(
            number=number,
            body_lines=len(body_lines),
            chars_per_full_line=float(statistics.median(full)) if full else None,
            font_chars=dict(fonts),
            body_size_pt=body_size_pt if body_lines else None,
            has_page_number=any(_in_band(line, height) and _PAGE_NUMBER.match(line.text)
                                for line in lines),
            is_full=(bool(body_lines) and span >= FULL_PAGE_RATIO * mean_span
                     and number < len(raw)),  # the text ends on the last page
            text="\n".join(line.text for line in lines),
        ))
    return pages


# --- sections ----------------------------------------------------------------------------

def _norm(text: str) -> str:
    return " ".join(text.split()).casefold()


def _heading_key(text: str) -> str:
    """Normalized heading text without leading numbering ("1.2 ", "Capitolo 3 - ", "IV. ")."""
    return _NUMBERING.sub("", _norm(text), count=1)


def _locate(pages, title: str, first: int) -> int | None:
    """Page of a heading, searching pages >= first, page 1 (title page) only as a fallback.

    In order: the first page after 1 with a line that is the title; page 1 with such a line
    (a draft without a title page); the first page after 1 whose text contains the title.
    Preferring a whole line skips table-of-contents entries ("Introduzione 3") and
    mentions in the prose that come before the heading itself.
    """
    key = _heading_key(title)
    pattern = re.compile(r"(?<!\w)" + re.escape(key) + r"(?!\w)")
    after_title_page = [p for p in pages if p.number >= max(first, 2)]
    title_page = [p for p in pages if p.number == 1] if first == 1 else []
    for p in after_title_page + title_page:
        if any(_heading_key(line) == key for line in p.text.splitlines()):
            return p.number
    for p in after_title_page:
        if pattern.search(_norm(p.text)):
            return p.number
    return None


def section_spans(pages: list[PageStats], headings: list[dict]) -> list[SectionSpan]:
    """Page span of each heading found in the PDF (headings not found are left out).

    Headings are searched in document order, each from the page of the previous one. A
    section ends on the page before the next heading of the same or a higher level (on its
    own start page if that heading is on the same page), or on the last page.
    """
    located, first = [], 1
    for h in headings:
        title, level = " ".join((h.get("text") or "").split()), h.get("heading_level")
        if not title or level is None or not _heading_key(title):
            continue
        start = _locate(pages, title, first)
        if start is not None:
            located.append((title, level, start))
            first = start
    last = max((p.number for p in pages), default=0)
    spans = []
    for i, (title, level, start) in enumerate(located):
        following = next((s for _, lv, s in located[i + 1:] if lv <= level), None)
        end = last if following is None else max(start, following - 1)
        spans.append(SectionSpan(title, level, start, end))
    return spans


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


def _per_page(rule, pages, rng, value, unit) -> Check:
    evaluated = [p for p in pages if p.number != 1 and p.is_full and value(p) is not None]
    if not evaluated:
        return Check(rule, True, f"not evaluated: no full text page after page 1 "
                                 f"({_allowed(rng)})", [])
    bad = [p for p in evaluated if not _in_range(value(p), rng)]
    if bad:
        parts = [f"page {p.number}: {_num(value(p))} {unit}" for p in bad[:MAX_LISTED_PAGES]]
        if len(bad) > MAX_LISTED_PAGES:
            parts.append(f"and {len(bad) - MAX_LISTED_PAGES} more pages")
        return Check(rule, False, "; ".join(parts) + f" ({_allowed(rng)})",
                     [p.number for p in bad])
    values = [value(p) for p in evaluated]
    lo, hi = min(values), max(values)
    amount = _num(lo) if lo == hi else f"{_num(lo)}–{_num(hi)}"
    return Check(rule, True, f"{amount} {unit} on full pages "
                             f"{_page_list(p.number for p in evaluated)} ({_allowed(rng)})", [])


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
    key = _heading_key(title)
    return any(re.match(re.escape(_norm(n)) + r"(?!\w)", key) for n in names)


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


def measure(doc, rules, workdir) -> Measurement:
    from .extract import extract

    doc = Path(doc)
    pdf = render_pdf(doc, workdir)
    pages = measure_pdf(pdf)
    sections = None
    if doc.suffix.lower() == ".docx":
        headings = [p for p in extract(doc)["paragraphs"] if p["heading_level"] is not None]
        sections = section_spans(pages, headings)
    return Measurement(str(doc), str(pdf), len(pages), pages, sections or [],
                       check_rules(pages, sections, rules))


# --- command -----------------------------------------------------------------------------

def add_arguments(parser):
    parser.add_argument("document", help="document to measure (.docx, .tex, .pdf)")
    parser.add_argument("--rules", required=True, help="linee-guida.yaml")
    parser.add_argument("--workdir", help="folder for the PDF (default: a new temporary folder, "
                                          "kept so that the PDF named in the output exists)")


def _summary(m: Measurement) -> str:
    failed = sum(not c.ok for c in m.checks)
    lines = [f"measured {m.source}: {m.page_count} pages (PDF: {m.pdf})"]
    lines += [f"{'OK  ' if c.ok else 'FAIL'} {c.rule}: {c.detail}" for c in m.checks]
    lines.append(f"{failed} of {len(m.checks)} checks failed" if failed else "all checks passed")
    return "\n".join(lines)


def run(args) -> int:
    from . import cli
    from .rules import RulesError, load_rules

    doc = Path(args.document)
    if not doc.is_file():
        print(f"error: file not found: {doc}", file=sys.stderr)
        return 2
    if cli.refuses_overwrite(doc, args):
        return 2
    try:
        rules = load_rules(args.rules)
    except RulesError as exc:
        for problem in exc.problems:
            print(f"error: {problem}", file=sys.stderr)
        return 2
    temporary = args.workdir is None
    workdir = Path(tempfile.mkdtemp(prefix="hmw-measure-")) if temporary else Path(args.workdir)
    try:
        m = measure(doc, rules, workdir)
    except RenderError as exc:
        print(f"error: {exc}", file=sys.stderr)
        if temporary:
            shutil.rmtree(workdir, ignore_errors=True)
        return 3 if exc.missing_tool else 2
    except Exception as exc:  # unreadable document or PDF
        print(f"error: cannot measure {doc.name} ({type(exc).__name__}: {exc})", file=sys.stderr)
        return 2
    data = asdict(m)
    for page in data["pages"]:
        del page["text"]  # the text is in extract.json; keep measure.json small for the reviewer
    cli.emit(data, args, text=_summary(m))
    return 0 if all(c.ok for c in m.checks) else 1
