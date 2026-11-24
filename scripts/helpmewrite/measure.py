"""Measure a rendered PDF against the guidelines.

Pages, font family and size, body lines per page, characters per line (spaces included),
page numbers and section lengths. Algorithm:
- words come from pdfplumber with font name and size; a line is a group of words whose
  top is within 2 pt; its text is the words joined by single spaces;
- the body size is the most frequent size, weighted by characters; body lines are within
  0.6 pt of it and outside the header/footer bands (top and bottom 7% of the page);
- a full line is 90-110% as wide as the reference width (see 4. below);
- a full page has body lines spanning at least 75% of the typical span (see 5. below);
- lines and characters per line are checked on full pages only, never on page 1 (title
  page); page numbers are checked on every page but page 1. The check details name the
  pages that were skipped and why; a check that can evaluate no page is not ok.

Departures from the plan's algorithm (accepted by the controller, rulings R6 and R7):
1. the last page is never full: the text ends there, so a page filled 75-95% would
   otherwise fail lines_per_page;
2. a heading is located on a page with a line that is the whole title (numbering stripped)
   before falling back to "the page text contains the title": table-of-contents entries
   ("Introduzione 3") and mentions in the prose would otherwise win;
3. page 1 is searched too, as a fallback for whole-line matches only, so a draft without a
   title page still finds an introduction on page 1;
4. the reference width is the 90th percentile of body-line widths, not the widest line:
   one line wider than the text area (a table kept at its old width, a long URL) would
   otherwise leave every prose line short of 90% and void chars_per_line;
5. a full page must also reach 90% of the typical bottom (the median of the pages' lowest
   body-line bottoms, without page 1 and the last page) and have no gap between body lines
   wider than 4 line pitches; the typical span is such a median too, not the mean. Pages
   that end early (before a figure that did not fit, a page-break heading, footnotes) and
   pages interrupted by a figure have fewer lines by design and would otherwise fail.

The rule checks live in checks.py; Check and check_rules are re-exported here.
"""
import re
import shutil
import statistics
import sys
import tempfile
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from .checks import Check, check_rules, heading_key, normalize_text
from .render import RenderError, render_pdf

LINE_TOP_TOLERANCE_PT = 2.0
WORD_JOIN_GAP_PT = 0.5      # fragments of one word split by a font change mid-word
BAND = 0.07                 # header and footer bands: top and bottom 7% of the page
BODY_SIZE_TOLERANCE_PT = 0.6
FULL_LINE_RATIO = 0.90
FULL_LINE_MAX_RATIO = 1.10  # wider than the text area: a table or an overflowing URL
FULL_PAGE_RATIO = 0.75
FULL_PAGE_BOTTOM_RATIO = 0.90
MAX_GAP_PITCHES = 4.0       # a wider gap between body lines is a figure or a table

_PAGE_NUMBER = re.compile(r"^\W*\d+\W*$|^(pag\.?|pagina|page)\s*\d+", re.IGNORECASE)
_SUBSET_PREFIX = re.compile(r"^[A-Z]{6}\+")


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


def _reference_width(body) -> float:
    """90th percentile of body-line widths: a few overflowing lines cannot set it."""
    widths = [line.width for lines in body for line in lines]
    if len(widths) < 2:
        return widths[0] if widths else 0.0
    return statistics.quantiles(widths, n=10, method="inclusive")[-1]


def _typical_pitch(body) -> float:
    """Median distance between consecutive body lines of a page (within a paragraph)."""
    steps = [b.top - a.top for lines in body for a, b in zip(lines, lines[1:]) if b.top > a.top]
    return statistics.median(steps) if steps else 0.0


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
    reference = _reference_width(body)
    # typical page: neither the title page nor the last page, which is short by design
    typical = ([lines for lines in body[1:-1] if lines] or [lines for lines in body[1:] if lines]
               or [lines for lines in body if lines])
    typical_bottom = statistics.median(lines[-1].bottom for lines in typical) if typical else 0.0
    typical_span = (statistics.median(lines[-1].bottom - lines[0].top for lines in typical)
                    if typical else 0.0)
    max_gap = MAX_GAP_PITCHES * _typical_pitch(body)

    def is_full(body_lines, number):
        if not body_lines or number == len(raw):  # the text ends on the last page
            return False
        gaps = [b.top - a.top for a, b in zip(body_lines, body_lines[1:])]
        return (body_lines[-1].bottom >= FULL_PAGE_BOTTOM_RATIO * typical_bottom
                and body_lines[-1].bottom - body_lines[0].top >= FULL_PAGE_RATIO * typical_span
                and max(gaps, default=0.0) <= max_gap)

    pages = []
    for number, ((height, lines), body_lines) in enumerate(zip(raw, body), start=1):
        full = [len(line.text) for line in body_lines
                if FULL_LINE_RATIO * reference <= line.width <= FULL_LINE_MAX_RATIO * reference]
        fonts = sum((line.fonts for line in body_lines), Counter())
        pages.append(PageStats(
            number=number,
            body_lines=len(body_lines),
            chars_per_full_line=float(statistics.median(full)) if full else None,
            font_chars=dict(fonts),
            body_size_pt=body_size_pt if body_lines else None,
            has_page_number=any(_in_band(line, height) and _PAGE_NUMBER.match(line.text)
                                for line in lines),
            is_full=is_full(body_lines, number),
            text="\n".join(line.text for line in lines),
        ))
    return pages


# --- sections ----------------------------------------------------------------------------

def _locate(pages, title: str, first: int) -> int | None:
    """Page of a heading, searching pages >= first, page 1 (title page) only as a fallback.

    In order: the first page after 1 with a line that is the title; page 1 with such a line
    (a draft without a title page); the first page after 1 whose text contains the title.
    Preferring a whole line skips table-of-contents entries ("Introduzione 3") and
    mentions in the prose that come before the heading itself.
    """
    key = heading_key(title)
    pattern = re.compile(r"(?<!\w)" + re.escape(key) + r"(?!\w)")
    after_title_page = [p for p in pages if p.number >= max(first, 2)]
    title_page = [p for p in pages if p.number == 1] if first == 1 else []
    for p in after_title_page + title_page:
        if any(heading_key(line) == key for line in p.text.splitlines()):
            return p.number
    for p in after_title_page:
        if pattern.search(normalize_text(p.text)):
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
        if not title or level is None or not heading_key(title):
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
