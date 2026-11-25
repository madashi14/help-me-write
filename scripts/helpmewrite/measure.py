"""Measure a rendered PDF against the guidelines.

Pages, font family and size, body lines per page, characters per line (spaces included),
page numbers and section lengths. Algorithm:
1. words and lines: words come from pdfplumber, with font name and size, split where two
   letters are more than WORD_GAP_PT apart (with pdfplumber's 3 pt the narrow spaces of
   TeX's justified text are lost); a line is a group of words whose top is within 2 pt, its
   text the words joined by single spaces. Two consecutive lines whose boxes overlap by
   more than half the smaller height are one line (a minus sign raised in a formula).
   The body size is the most frequent size, weighted by characters; body lines are within
   0.6 pt of it and are not margin lines (4.);
2. pitch: the median step between consecutive lines at the body size, without those in the
   fixed header and footer bands (top and bottom 7% of the page);
3. margin positions: on each page the last line is a footer candidate when it is alone on
   the page or more than MARGIN_GAP_PITCHES below the line before it; the first line is a
   header candidate in the same way. A line larger than the body size is never a candidate:
   running headers and footers are not, chapter titles at the top of a page are (ruling
   R9-1). A position (top within MARGIN_TOLERANCE_PT) shared by
   candidates on at least MARGIN_SHARE of the pages with text is a margin position: a page
   number about 2 cm from the edge (LaTeX) is outside the 7% bands;
4. margin lines: the lines in the 7% bands, plus the first or last line of a page within
   MARGIN_TOLERANCE_PT of a header or footer position. A margin line is never a body
   line; page numbers (_PAGE_NUMBER) are looked for among margin lines only;
5. full page: the line slots around and between its body lines are summed in fractions of
   the pitch, before rounding: above the first body line (from the typical top), inside the
   page (steps wider than the paragraph step plus half a pitch) and below the last one (to
   the typical bottom). A gap holding a line that is neither body nor margin (a heading, a
   caption, a footnote) is occupied, any other is empty (a figure without a caption, a
   text that ends early). A page is full when round(empty) <= MISSING_SLOTS and it is not
   the last page; its line slots are its body lines plus round(occupied). The typical top
   is the lower quartile of the pages' first body-line tops, the typical bottom the upper
   quartile of their last body-line bottoms, without the first and the last page: pages
   that start lower (a chapter title on top) or end early (the end of a chapter), often
   half of a short document with a chapter per page, do not move them (R9-3). The
   paragraph step is the pitch, or the usual wider step between paragraphs when the
   document has paragraph spacing;
6. full prose lines: a body line 90-110% as wide as the reference width, unless two
   consecutive words are more than PROSE_GAP_SIZES times the body size apart (a table of
   contents entry with the page number on the right, a table row) or it has leader dots
   (three or more). chars_per_full_line is their median, or None with fewer than
   MIN_FULL_LINES of them or when most of the page's full lines are not prose (a table of
   contents whose entries end close to their page numbers, without leader dots).
Lines per page are checked on full pages (their line slots), characters per line on every
page with chars_per_full_line, never on page 1 (title page); page numbers are checked on
every page but page 1. The check details name the pages that were skipped and why; a check
that can evaluate no page is not ok.

Departures from the plan's algorithm still in force (accepted by the controller, rulings
R6 and R7):
1. the last page is never full: the text ends there, so a page filled 75-95% would
   otherwise fail lines_per_page;
2. a heading is located on a page with a line that is the whole title (numbering stripped)
   before falling back to "the page text contains the title": table-of-contents entries
   ("Introduzione 3") and mentions in the prose would otherwise win;
3. page 1 is searched too, as a fallback for whole-line matches only, so a draft without a
   title page still finds an introduction on page 1;
4. the reference width is the 90th percentile of body-line widths, not the widest line:
   one line wider than the text area (a table kept at its old width, a long URL) would
   otherwise leave every prose line short of 90% and void chars_per_line.

The rule checks live in checks.py; Check and check_rules are re-exported here.
"""
import re
import shutil
import statistics
import sys
import tempfile
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .checks import MIN_FULL_LINES, Check, check_rules, heading_key, normalize_text
from .render import RenderError, render_pdf

WORD_GAP_PT = 1.5           # wider gaps between letters split words (TeX's narrow spaces)
LINE_TOP_TOLERANCE_PT = 2.0
WORD_JOIN_GAP_PT = 0.5      # fragments of one word split by a font change mid-word
BAND = 0.07                 # fixed header and footer bands: top and bottom 7% of the page
BODY_SIZE_TOLERANCE_PT = 0.6
MARGIN_GAP_PITCHES = 1.5    # a first/last line this far from the text: header/footer candidate
MARGIN_TOLERANCE_PT = 2.0   # candidates within this distance share a position
MARGIN_SHARE = 0.3          # of the pages with text, for a position to be a margin position
FULL_LINE_RATIO = 0.90
FULL_LINE_MAX_RATIO = 1.10  # wider than the text area: a table or an overflowing URL
PROSE_GAP_SIZES = 2.0       # a wider gap between words (in body sizes): not a line of prose
MISSING_SLOTS = 1           # empty line slots a full page may have
WIDE_STEP_PITCHES = 1.15    # a wider step between body lines is not inside a paragraph
PARAGRAPH_STEP_SHARE = 0.05  # wider steps this frequent are paragraph spacing, not headings

_ROMAN = r"(?=[ivx])x{0,3}(?:ix|iv|v?i{0,3})(?<=[ivx])"  # i ... xxxix (front matter)
_PAGE_NUMBER = re.compile(rf"^\W*(?:\d+|{_ROMAN})\W*$|^(pag\.?|pagina|page)\s*(?:\d+|{_ROMAN}\b)",
                          re.IGNORECASE)
_LEADER_DOTS = re.compile(r"(?:\.\s?){3,}")
_SUBSET_PREFIX = re.compile(r"^[A-Z]{6}\+")


@dataclass
class PageStats:
    number: int
    body_lines: int
    line_slots: int | None              # body lines + slots taken by headings, captions,
                                        # footnotes; None when the page is not full
    chars_per_full_line: float | None   # median over the page's full prose lines; None with
                                        # fewer than MIN_FULL_LINES of them
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
    headings_source: str = "none"  # "docx", "tex", "pdf-bookmarks" or "none" (headings.py)


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
    words: list = field(default_factory=list, repr=False)  # pdfplumber words, left to right

    @property
    def size(self) -> float:
        return self.sizes.most_common(1)[0][0]

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.bottom - self.top


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
                 words[0]["x0"], max(w["x1"] for w in words), sizes, fonts, words)


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


def _join(a: _Line, b: _Line) -> _Line:
    """One line from two fragments; lines built without words join their texts left to
    right."""
    if a.words and b.words:
        return _make_line(a.words + b.words)
    left, right = sorted((a, b), key=lambda line: line.x0)
    return _Line(f"{left.text} {right.text}", min(a.top, b.top), max(a.bottom, b.bottom),
                 min(a.x0, b.x0), max(a.x1, b.x1), a.sizes + b.sizes, a.fonts + b.fonts)


def _merge_overlapping(lines) -> list[_Line]:
    """Join consecutive lines whose boxes overlap by more than half the smaller height:
    the fragments of one line of a formula (a raised minus sign and the rest)."""
    merged = []
    for line in lines:
        if merged:
            prev = merged[-1]
            overlap = min(prev.bottom, line.bottom) - max(prev.top, line.top)
            if overlap > 0.5 * min(prev.height, line.height):
                merged[-1] = _join(prev, line)
                continue
        merged.append(line)
    return merged


def _in_band(line: _Line, height: float) -> bool:
    middle = (line.top + line.bottom) / 2
    return middle < BAND * height or middle > (1 - BAND) * height


def _reference_width(body) -> float:
    """90th percentile of body-line widths: a few overflowing lines cannot set it."""
    widths = [line.width for lines in body for line in lines]
    if len(widths) < 2:
        return widths[0] if widths else 0.0
    return statistics.quantiles(widths, n=10, method="inclusive")[-1]


def _steps(lines) -> list[float]:
    return [b.top - a.top for a, b in zip(lines, lines[1:]) if b.top > a.top]


def _typical_pitch(body) -> float:
    """Median distance between consecutive body lines of a page (within a paragraph)."""
    steps = [step for lines in body for step in _steps(lines)]
    return statistics.median(steps) if steps else 0.0


def _paragraph_step(body, pitch: float) -> float:
    """The usual step between two paragraphs: the pitch, or pitch plus paragraph spacing.

    Wider steps are paragraph spacing when one value of them is frequent (every few lines);
    headings and figures are rarer and their steps vary.
    """
    steps = [step for lines in body for step in _steps(lines)]
    wide = [step for step in steps if step > WIDE_STEP_PITCHES * pitch]
    if not wide:
        return pitch
    usual = Counter(round(step) for step in wide).most_common(1)[0][0]
    near = [step for step in wide if abs(step - usual) <= 1.0]
    return statistics.median(near) if len(near) >= PARAGRAPH_STEP_SHARE * len(steps) else pitch


def _positions(candidates, pages_with_text) -> list[float]:
    """Tops shared, within MARGIN_TOLERANCE_PT, by at least MARGIN_SHARE of the pages: the
    median of each group of candidates, the most shared first."""
    def near(top):
        return [c for c in candidates if abs(c - top) <= MARGIN_TOLERANCE_PT]

    positions = []
    for top in sorted(candidates, key=lambda c: -len(near(c))):
        if len(near(top)) < MARGIN_SHARE * pages_with_text:
            break
        if all(abs(top - p) > MARGIN_TOLERANCE_PT for p in positions):
            positions.append(statistics.median(near(top)))
    return positions


def margin_positions(pages: list[list[_Line]], pitch: float,
                     body_size_pt: float | None = None) -> tuple[list[float], list[float]]:
    """Tops of the header and footer lines that recur on the pages (see 3. above).

    With body_size_pt, a first or last line larger than the body size (a chapter title at
    the top of a page) is not a candidate; None considers every size.
    """
    def not_larger(line):
        return body_size_pt is None or line.size <= body_size_pt + BODY_SIZE_TOLERANCE_PT

    headers, footers = [], []
    for lines in pages:
        if not lines:
            continue
        if (len(lines) == 1 or lines[1].top - lines[0].top > MARGIN_GAP_PITCHES * pitch) \
                and not_larger(lines[0]):
            headers.append(lines[0].top)
        if (len(lines) == 1 or lines[-1].top - lines[-2].top > MARGIN_GAP_PITCHES * pitch) \
                and not_larger(lines[-1]):
            footers.append(lines[-1].top)
    with_text = sum(1 for lines in pages if lines)
    return _positions(headers, with_text), _positions(footers, with_text)


def typical_bounds(pages: list[list[_Line]]) -> tuple[float, float]:
    """(typical top, typical bottom) of the text on pages of body lines (see 5. above):
    lower quartile of the first tops, upper quartile of the last bottoms; (0, 0) without
    pages."""
    pages = [lines for lines in pages if lines]
    if not pages:
        return 0.0, 0.0
    if len(pages) == 1:
        return pages[0][0].top, pages[0][-1].bottom
    tops = statistics.quantiles([lines[0].top for lines in pages], n=4, method="inclusive")
    bottoms = statistics.quantiles([lines[-1].bottom for lines in pages], n=4,
                                   method="inclusive")
    return tops[0], bottoms[-1]


def slot_counts(body, others, typical_top: float, typical_bottom: float, pitch: float,
                paragraph_step: float) -> tuple[float, float]:
    """(empty, occupied) line slots of a page, in fractions of the pitch (see 5. above).

    body are the page's body lines, others its lines that are neither body nor margin.
    """
    empty = occupied = 0.0
    if not body or pitch <= 0:
        return empty, occupied
    first, last = body[0], body[-1]
    gaps = [(max(0.0, (first.top - typical_top) / pitch),
             any(o.top < first.top for o in others))]
    for a, b in zip(body, body[1:]):
        step = b.top - a.top
        if step > paragraph_step + 0.5 * pitch:
            gaps.append(((step - paragraph_step) / pitch,
                         any(a.top < o.top < b.top for o in others)))
    gaps.append((max(0.0, (typical_bottom - last.bottom) / pitch),
                 any(o.top > last.top for o in others)))
    for slots, holds_other in gaps:
        if holds_other:
            occupied += slots
        else:
            empty += slots
    return empty, occupied


def _is_prose(line: _Line, body_size_pt: float) -> bool:
    """Not a table-of-contents entry (leader dots, or the page number pushed to the right)
    nor a table row: no gap between two words wider than PROSE_GAP_SIZES body sizes."""
    if _LEADER_DOTS.search(line.text):
        return False
    gap = PROSE_GAP_SIZES * body_size_pt
    return all(b["x0"] - a["x1"] <= gap for a, b in zip(line.words, line.words[1:]))


def _chars_per_full_line(body_lines, reference: float, body_size_pt: float) -> float | None:
    """Median characters of a page's full prose lines (see 6. above); None with fewer than
    MIN_FULL_LINES of them, or with more full lines that are not prose than lines that are."""
    full = [line for line in body_lines
            if FULL_LINE_RATIO * reference <= line.width <= FULL_LINE_MAX_RATIO * reference]
    prose = [len(line.text) for line in full if _is_prose(line, body_size_pt)]
    if len(prose) < MIN_FULL_LINES or len(full) - len(prose) > len(prose):
        return None
    return float(statistics.median(prose))


def measure_pdf(pdf, body_size_pt: float | None = None) -> list[PageStats]:
    import pdfplumber

    with pdfplumber.open(str(pdf)) as doc:
        raw = [(page.height, _merge_overlapping(_lines(page.extract_words(
                    x_tolerance=WORD_GAP_PT, extra_attrs=["fontname", "size"]))))
               for page in doc.pages]

    if body_size_pt is None:
        sizes = sum((line.sizes for _, lines in raw for line in lines), Counter())
        body_size_pt = sizes.most_common(1)[0][0] if sizes else None

    def body_sized(line):
        return body_size_pt is not None and abs(line.size - body_size_pt) <= BODY_SIZE_TOLERANCE_PT

    pitch = _typical_pitch([[line for line in lines
                             if body_sized(line) and not _in_band(line, height)]
                            for height, lines in raw])
    headers, footers = margin_positions([lines for _, lines in raw], pitch, body_size_pt)

    def is_margin(line, lines, height):
        def near(positions):
            return any(abs(line.top - p) <= MARGIN_TOLERANCE_PT for p in positions)
        return (_in_band(line, height) or (line is lines[0] and near(headers))
                or (line is lines[-1] and near(footers)))

    margin, body, others = [], [], []  # per page: margin lines, body lines, the other lines
    for height, lines in raw:
        margin.append([])
        body.append([])
        others.append([])
        for line in lines:
            if is_margin(line, lines, height):
                margin[-1].append(line)
            elif body_sized(line):
                body[-1].append(line)
            else:
                others[-1].append(line)
    reference = _reference_width(body)
    # typical page: neither the title page nor the last page, which is short by design
    typical = ([lines for lines in body[1:-1] if lines] or [lines for lines in body[1:] if lines]
               or [lines for lines in body if lines])
    typical_top, typical_bottom = typical_bounds(typical)
    paragraph_step = _paragraph_step(body, pitch)

    pages = []
    for number, ((_, lines), edge, body_lines, other) in enumerate(
            zip(raw, margin, body, others), start=1):
        empty, occupied = slot_counts(body_lines, other, typical_top, typical_bottom, pitch,
                                      paragraph_step)
        # the text ends on the last page: it is never full
        full = bool(body_lines) and number != len(raw) and round(empty) <= MISSING_SLOTS
        fonts = sum((line.fonts for line in body_lines), Counter())
        pages.append(PageStats(
            number=number,
            body_lines=len(body_lines),
            line_slots=len(body_lines) + round(occupied) if full else None,
            chars_per_full_line=_chars_per_full_line(body_lines, reference, body_size_pt),
            font_chars=dict(fonts),
            body_size_pt=body_size_pt if body_lines else None,
            has_page_number=any(_PAGE_NUMBER.match(line.text) for line in edge),
            is_full=full,
            text="\n".join(line.text for line in lines),
        ))
    return pages


# --- sections ----------------------------------------------------------------------------

MAX_TITLE_LINES = 3  # a heading wrapped over up to this many lines of a page


def _joined_lines(text: str):
    """The page's lines, and its runs of up to MAX_TITLE_LINES consecutive lines joined by a
    space (a line ending in a hyphen joins the next one without hyphen or space)."""
    lines = text.splitlines()
    for i in range(len(lines)):
        joined = ""
        for line in lines[i:i + MAX_TITLE_LINES]:
            joined = joined[:-1] + line.lstrip() if joined.endswith("-") else (
                f"{joined} {line}" if joined else line)
            yield joined


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
        if any(heading_key(line) == key for line in _joined_lines(p.text)):
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
    from .headings import document_headings

    doc = Path(doc)
    pdf = render_pdf(doc, workdir)
    pages = measure_pdf(pdf)
    headings, source = document_headings(doc, pdf)
    sections = section_spans(pages, headings) if headings is not None else None
    return Measurement(str(doc), str(pdf), len(pages), pages, sections or [],
                       check_rules(pages, sections, rules, source), source)


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
