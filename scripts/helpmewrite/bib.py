"""Bibliography and citation extraction, and matching of entries to local PDF sources.

Citation `paragraph` ids are the ids `extract` produces (docx: index in
iter_body_paragraphs; tex: paragraph id, with file and line from extract_tex).
"""
import re
import sys
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import cli
from .extract import extract

MAX_PDF_BYTES = 50 * 1024 * 1024
SOURCE_PAGES = 2


class BibError(Exception):
    pass


@dataclass
class BibEntry:
    key: str
    raw: str
    title: str | None
    authors: list[str]
    year: str | None
    doi: str | None
    venue: str | None
    paragraph: int | None


@dataclass
class Citation:
    key: str
    paragraph: int | None
    file: str | None
    line: int | None
    sentence: str


@dataclass
class BibReport:
    style: str
    entries: list[BibEntry] = field(default_factory=list)
    citations: list[Citation] = field(default_factory=list)
    uncited_entries: list[str] = field(default_factory=list)
    missing_entries: list[str] = field(default_factory=list)
    local_sources: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------- text helpers

def _strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def _words(text: str) -> list[str]:
    return re.findall(r"[^\W_]+", _strip_accents(text).lower())


def _surname_key(name: str) -> str:
    return "".join(c for c in _strip_accents(name).lower() if c.isalpha())


_ABBREV = ("et al.", "es.", "p.", "pp.", "cfr.", "fig.", "vol.", "n.", "e.g.", "i.e.")


def _sentence_spans(text: str) -> list[tuple[int, int]]:
    spans, start, depth = [], 0, 0
    for i, ch in enumerate(text):
        if ch in "[(":
            depth += 1
        elif ch in "])":
            depth = max(0, depth - 1)
        elif ch in ".?!" and depth == 0 and i + 1 < len(text) and text[i + 1].isspace():
            head = text[start:i + 1].lower()
            if ch == "." and (head.endswith(_ABBREV)
                              or re.search(r"(?<![^\W\d_])[A-Z]\.$", text[start:i + 1])):
                continue
            spans.append((start, i + 1))
            start = i + 1
            while start < len(text) and text[start].isspace():
                start += 1
    if start < len(text):
        spans.append((start, len(text)))
    return spans


def split_sentences(text: str) -> list[str]:
    return [text[a:b].strip() for a, b in _sentence_spans(text)]


def _sentence_at(text: str, pos: int) -> str:
    for a, b in _sentence_spans(text):
        if a <= pos < b or pos < a:
            return text[a:b].strip()
    return text.strip()


# ------------------------------------------------------------ entry parsing

_YEAR = re.compile(r"(?<!\w)((?:19|20)\d{2})([a-z]?)(?!\w)")
_DOI = re.compile(r"10\.\d{4,9}/\S+")
_NUM_PREFIX = re.compile(r"^\s*\[(\d+)\]\s*")


def _clean_latex(s: str) -> str:
    return " ".join(s.replace("{", "").replace("}", "").split())


def _first_surname(head: str) -> str:
    """Surname of the first author in text like 'Rossi, M., Verdi, A.' or 'M. Rossi'."""
    head = re.split(r"\bet\s+al\b|\s&\s|\s(?:and|e)\s|;", head, maxsplit=1)[0]
    if "," in head:
        head = head.split(",", 1)[0]
    tokens = [t for t in head.split() if not re.fullmatch(r"[A-Z]\.?(-?[A-Z]\.?)*", t)]
    return " ".join(tokens)


def _authors_from_text(head: str) -> list[str]:
    found = re.findall(r"([^,;&]+?,\s*(?:[A-Z][\w-]*\.\s*)+)", head + " ")
    if found:
        return [a.strip().rstrip(",") for a in found]
    head = head.strip(" .,")
    return [head] if head else []


def parse_text_entry(raw: str, key: str | None, position: int, paragraph: int | None) -> tuple[BibEntry, str]:
    body = _NUM_PREFIX.sub("", raw).strip()
    m = _YEAR.search(body)
    year = m.group(1) if m else None
    suffix = m.group(2) if m else ""
    doi_m = _DOI.search(body)
    doi = doi_m.group(0).rstrip(".,;)") if doi_m else None
    head = body[:m.start()].rstrip(" (") if m else ""
    title = venue = None
    q = re.search(r'["“«]([^"”»]+)["”»]', body)
    after = re.search(r"\(\s*(?:19|20)\d{2}[a-z]?\s*\)\s*\.?\s*(.+)", body) if m else None
    rest = None
    if q:
        title = q.group(1).strip(" .,")
        rest = body[q.end():].lstrip(" .,")
    elif after:
        parts = re.split(r"\.\s+", after.group(1), maxsplit=1)
        title = parts[0].strip(" .,") or None
        rest = parts[1] if len(parts) > 1 else None
    if rest:
        venue = re.split(r"[,.]\s|\.$|\s+doi|\s+https?:", rest, maxsplit=1)[0].strip(" .,") or None
    authors = _authors_from_text(head) if head else []
    if key is None:
        m_num = _NUM_PREFIX.match(raw)
        if m_num:
            key = f"[{m_num.group(1)}]"
        else:
            key = f"[{position}]"
    return BibEntry(key, raw.strip(), title, authors, year, doi, venue, paragraph), \
        (_surname_key(_first_surname(head or body)) + (year or "") + suffix)


def _bibtex_entries(path: Path) -> list[BibEntry]:
    import bibtexparser
    from bibtexparser.bparser import BibTexParser

    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        parser = BibTexParser(common_strings=True, ignore_nonstandard_types=False)
        db = bibtexparser.loads(text, parser)
    except Exception as exc:
        raise BibError(f"cannot read bibliography {path.name} ({type(exc).__name__}: {exc})")
    entries = []
    for e in db.entries:
        year_m = _YEAR.search(e.get("year", "") or e.get("date", ""))
        authors = [_clean_latex(a) for a in re.split(r"\s+and\s+", e.get("author", "")) if a.strip()]
        doi = e.get("doi") or None
        if doi:
            doi = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", doi.strip(), flags=re.I)
        venue = next((_clean_latex(e[k]) for k in ("journal", "journaltitle", "booktitle",
                                                   "publisher") if e.get(k)), None)
        title = _clean_latex(e["title"]) if e.get("title") else None
        raw = " ".join(x for x in (
            "; ".join(authors), f"({year_m.group(1)})." if year_m else "",
            f"{title}." if title else "", f"{venue}." if venue else "") if x)
        entries.append(BibEntry(e["ID"], raw, title, authors, year_m.group(1) if year_m else None,
                                doi, venue, None))
    return entries


# --------------------------------------------------------- citation scanning

_DASH = "–—-"
_NUM_CITE = re.compile(
    rf"\[\s*(\d+(?:\s*[{_DASH}]\s*\d+)?(?:\s*[,;]\s*\d+(?:\s*[{_DASH}]\s*\d+)?)*)\s*\]")
_PARTICLES = r"(?:[Dd]e|[Dd]i|[Vv]an|[Vv]on|[Dd]er|[Dd]el|[Dd]ella|[Ll]a|[Ll]e|[Dd]os)"
_CAP = r"[A-ZÀ-Ý][\w'’\-]+"
_NARRATIVE = re.compile(
    rf"((?:{_PARTICLES}\s+)*{_CAP})(?:\s+et\s+al\.?|\s+(?:e|and|&)\s+{_CAP})?"
    r"\s*\(((?:19|20)\d{2}[a-z]?)\)")
_PAREN = re.compile(r"\(([^()]*?(?:19|20)\d{2}[a-z]?[^()]*?)\)")
_AY_PART = re.compile(r"^(?P<name>[^\d]*?)[,\s]*(?P<year>(?:19|20)\d{2}[a-z]?)\b")
_LEAD = re.compile(r"^(?:cfr\.?|vedi|see|e\.g\.|es\.|i\.e\.|cf\.?)\s+", re.I)
_TEX_CITE = re.compile(
    r"\\(?:cite|citep|citet|parencite|textcite|autocite)\*?(?:\[[^\]]*\]){0,2}\{([^}]*)\}")


def expand_numeric(body: str) -> list[int]:
    out = []
    for part in re.split(r"[,;]", body):
        nums = [int(n) for n in re.findall(r"\d+", part)]
        if len(nums) == 2 and 0 <= nums[1] - nums[0] <= 1000:
            out.extend(range(nums[0], nums[1] + 1))
        elif nums:
            out.extend(nums[:1] if len(nums) == 1 else nums)
    return out


def _author_year_key(name: str, year: str) -> str | None:
    name = _LEAD.sub("", name.strip(" ,;"))
    name = re.split(r"\bet\s+al\b|\s&\s|\s(?:and|e)\s", name, maxsplit=1)[0]
    surname = _surname_key(name)
    return surname + year if surname else None


def _scan_numeric(text: str) -> list[tuple[int, str]]:
    return [(m.start(), f"[{n}]") for m in _NUM_CITE.finditer(text)
            for n in expand_numeric(m.group(1))]


def _scan_author_year(text: str) -> list[tuple[int, str]]:
    found = []
    for m in _PAREN.finditer(text):
        for part in m.group(1).split(";"):
            pm = _AY_PART.match(part.strip())
            key = _author_year_key(pm["name"], pm["year"]) if pm else None
            if key:
                found.append((m.start(), key))
    for m in _NARRATIVE.finditer(text):
        key = _author_year_key(m.group(1), m.group(2))
        if key:
            found.append((m.start(), key))
    return sorted(found, key=lambda x: x[0])


def _scan_latex(text: str) -> list[tuple[int, str]]:
    text = re.sub(r"(?<!\\)%.*", "", text)
    return [(m.start(), k.strip()) for m in _TEX_CITE.finditer(text)
            for k in m.group(1).split(",") if k.strip()]


# ------------------------------------------------------------ main extraction

_BIB_HEADING = re.compile(
    r"^\s*(?:\d+(?:\.\d+)*\.?\s*)?(?:bibliografia|riferimenti( bibliografici)?|references|"
    r"bibliography)\s*:?\s*$", re.IGNORECASE)


def _bib_files(paragraphs: list[dict], main: Path, explicit: Path | None) -> list[Path]:
    if explicit is not None:
        if not Path(explicit).is_file():
            raise BibError(f"bibliography file not found: {explicit}")
        return [Path(explicit)]
    names = []
    for p in paragraphs:
        text = re.sub(r"(?<!\\)%.*", "", p["text"])
        for m in re.finditer(r"\\(?:bibliography|addbibresource)\s*(?:\[[^\]]*\])?\{([^}]*)\}", text):
            names.extend(n.strip() for n in m.group(1).split(",") if n.strip())
    files = []
    for n in names:
        f = main.parent / (n if n.lower().endswith(".bib") else n + ".bib")
        if f.is_file() and f not in files:
            files.append(f)
    return files


def _split_body_and_entries(paragraphs: list[dict]) -> tuple[list[dict], list[dict]]:
    idx = None
    for i, p in enumerate(paragraphs):
        is_head = p.get("heading_level") is not None or "heading_level" not in p
        if is_head and _BIB_HEADING.match(p["text"]):
            idx = i
    if idx is None:
        return paragraphs, []
    return paragraphs[:idx], [p for p in paragraphs[idx + 1:] if p["text"].strip()]


def _finish(style, entries, cites) -> BibReport:
    keys = {e.key for e in entries}
    cited = {c.key for c in cites}
    missing = []
    for c in cites:
        if c.key not in keys and c.key not in missing:
            missing.append(c.key)
    return BibReport(style, entries, cites, [e.key for e in entries if e.key not in cited],
                     missing)


def extract_bibliography(doc: Path, bib: Path | None = None) -> BibReport:
    doc = Path(doc)
    data = extract(doc)
    paragraphs = data["paragraphs"]
    if data["format"] == "latex":
        entries = []
        for f in _bib_files(paragraphs, doc, bib):
            entries.extend(_bibtex_entries(f))
        cites = []
        for p in paragraphs:
            for pos, key in _scan_latex(p["text"]):
                cites.append(Citation(key, p["id"], p["file"], p["line"],
                                      _sentence_at(p["text"], pos)))
        return _finish("latex", entries, cites)

    body, entry_paras = _split_body_and_entries(paragraphs)
    numeric_hits = [(p, _scan_numeric(p["text"])) for p in body]
    year_re = re.compile(r"^\s*\[\d+\]")
    explicit_numeric = bool(entry_paras) and sum(
        1 for p in entry_paras if year_re.match(p["text"])) * 2 > len(entry_paras)
    # drop bracketed years such as "[2021]" unless an entry "[2021]" exists
    entry_numbers = {int(m.group(1)) for p in entry_paras if (m := _NUM_PREFIX.match(p["text"]))}
    numeric_hits = [(p, [(pos, k) for pos, k in hits
                         if not (1900 <= int(k[1:-1]) <= 2100 and int(k[1:-1]) not in entry_numbers)])
                    for p, hits in numeric_hits]
    ay_hits = [(p, _scan_author_year(p["text"])) for p in body]
    n_num = sum(len(h) for _, h in numeric_hits)
    n_ay = sum(len(h) for _, h in ay_hits)
    if explicit_numeric or n_num > n_ay:
        style, hits = "numeric", numeric_hits
    elif n_ay:
        style, hits = "author-year", ay_hits
    else:
        return BibReport("unknown", _entries_unknown(entry_paras))
    entries = []
    for pos, p in enumerate(entry_paras, start=1):
        if style == "numeric":
            e, _ = parse_text_entry(p["text"], None, pos, p["id"])
        else:
            e, key = parse_text_entry(p["text"], "", pos, p["id"])
            e.key = key
        entries.append(e)
    cites = [Citation(k, p["id"], None, None, _sentence_at(p["text"], pos))
             for p, h in hits for pos, k in h]
    return _finish(style, entries, cites)


def _entries_unknown(entry_paras) -> list[BibEntry]:
    out = []
    for pos, p in enumerate(entry_paras, start=1):
        e, key = parse_text_entry(p["text"], "", pos, p["id"])
        e.key = key or f"[{pos}]"
        out.append(e)
    return out


# ------------------------------------------------------------- local sources

def pdf_pages_text(pdf: Path, max_pages: int | None = None) -> list[str]:
    import pdfplumber

    with pdfplumber.open(str(pdf)) as doc:
        pages = doc.pages if max_pages is None else doc.pages[:max_pages]
        return [page.extract_text() or "" for page in pages]


def find_local_sources(folder: Path, entries: list[BibEntry],
                       skipped: list[str] | None = None) -> dict[str, str]:
    """Map entry key -> PDF path found under folder (recursive). Broken or oversized PDFs
    are skipped (their paths are appended to `skipped` if given)."""
    folder = Path(folder)
    found: dict[str, str] = {}
    candidates = [e for e in entries if e.doi or (e.title and _words(e.title))]
    for pdf in sorted(folder.rglob("*.pdf")):
        if ".help-me-write" in pdf.relative_to(folder).parts:
            continue
        try:
            if pdf.stat().st_size > MAX_PDF_BYTES:
                raise ValueError("too large")
            text = "\n".join(pdf_pages_text(pdf, SOURCE_PAGES))
        except Exception:
            if skipped is not None:
                skipped.append(str(pdf))
            continue
        lowered = text.lower()
        compact = re.sub(r"\s+", "", lowered)
        wordset = set(_words(text))
        for e in candidates:
            if e.key in found:
                continue
            if e.doi and (e.doi.lower() in lowered or e.doi.lower() in compact):
                found[e.key] = str(pdf)
                continue
            tw = [w for w in _words(e.title or "") if len(w) >= 3]
            if tw and sum(w in wordset for w in tw) / len(tw) >= 0.8:
                found[e.key] = str(pdf)
    return found


# ------------------------------------------------------------------- commands

def add_bib_arguments(parser):
    parser.add_argument("document", help="document to read (.docx, .tex, .pdf)")
    parser.add_argument("--bib", help="BibTeX file (LaTeX only; default: from \\bibliography)")
    parser.add_argument("--sources", help="folder with source PDFs to match against entries")


def run_bib(args) -> int:
    path = Path(args.document)
    if not path.is_file():
        print(f"error: file not found: {path}", file=sys.stderr)
        return 2
    if cli.refuses_overwrite(path, args):
        return 2
    if args.sources and not Path(args.sources).is_dir():
        print(f"error: sources folder not found: {args.sources}", file=sys.stderr)
        return 2
    try:
        report = extract_bibliography(path, Path(args.bib) if args.bib else None)
    except (BibError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"error: cannot read {path.name} as a valid document "
              f"({type(exc).__name__}: {exc})", file=sys.stderr)
        return 2
    if args.sources:
        report.local_sources = find_local_sources(Path(args.sources), report.entries)
    data = asdict(report)
    lines = [f"style: {report.style}",
             f"entries: {len(report.entries)}, citations: {len(report.citations)}",
             f"missing entries (cited, not in bibliography): {', '.join(report.missing_entries) or '-'}",
             f"uncited entries: {', '.join(report.uncited_entries) or '-'}"]
    lines += [f"local source {k}: {v}" for k, v in report.local_sources.items()]
    cli.emit(data, args, text="\n".join(lines))
    return 0


def add_pdftext_arguments(parser):
    parser.add_argument("pdf", help="PDF to read; output: {\"pages\": [{\"page\": 1, \"text\": ...}]}"
                                    " with 1-based page numbers")


def run_pdftext(args) -> int:
    path = Path(args.pdf)
    if not path.is_file():
        print(f"error: file not found: {path}", file=sys.stderr)
        return 2
    if cli.refuses_overwrite(path, args):
        return 2
    try:
        pages = pdf_pages_text(path)
    except Exception as exc:
        print(f"error: cannot read {path.name} as a PDF ({type(exc).__name__}: {exc})",
              file=sys.stderr)
        return 2
    data = {"pages": [{"page": i, "text": t} for i, t in enumerate(pages, start=1)]}
    cli.emit(data, args, text="\n\n".join(f"--- page {i} ---\n{t}" for i, t in enumerate(pages, 1)))
    return 0
