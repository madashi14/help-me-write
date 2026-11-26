"""Paragraph extraction for docx, LaTeX and PDF.

For docx, the paragraph id is the index in iter_body_paragraphs(); reading and
writing (track_docx, bib) must use the same enumeration.
"""
import re
import sys
from pathlib import Path

from lxml import etree

from . import cli

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
_P, _R, _T = f"{{{W}}}p", f"{{{W}}}r", f"{{{W}}}t"
_FALLBACK = f"{{{MC}}}Fallback"
_STYLE_NAME = re.compile(r"^(?:heading|titolo)\s*(\d+)$", re.IGNORECASE)
_TOC_HEADING = re.compile(r"^(?:toc heading|titolo sommario)$", re.IGNORECASE)


def iter_body_paragraphs(doc) -> list:
    """All body w:p in document order (tables and text boxes included).

    Headers, footers and notes live in other parts. Text boxes are stored twice
    (mc:Choice and mc:Fallback): the fallback copy is skipped.
    """
    return [
        p for p in doc.element.body.iter(_P)
        if not any(a.tag == _FALLBACK for a in p.iterancestors())
    ]


def visible_text(p) -> str:
    """Text of direct runs, w:ins and w:hyperlink; deleted text is excluded."""
    out = []

    def walk(node):
        for child in node:
            tag = child.tag
            if tag == _R:
                for el in child:
                    if el.tag == _T:
                        out.append(el.text or "")
                    elif el.tag == f"{{{W}}}tab":
                        out.append("\t")
                    elif el.tag == f"{{{W}}}br":
                        out.append("\n")
            elif tag in (f"{{{W}}}ins", f"{{{W}}}hyperlink", f"{{{W}}}smartTag",
                         f"{{{W}}}sdt", f"{{{W}}}sdtContent"):
                walk(child)

    walk(p)
    return "".join(out)


def _heading_level(p, styles):
    ppr = p.find(f"{{{W}}}pPr")
    style_el = None
    if ppr is not None:
        sid = ppr.find(f"{{{W}}}pStyle")
        if sid is not None:
            style_el = styles.get(sid.get(f"{{{W}}}val"))
        lvl = ppr.find(f"{{{W}}}outlineLvl")
        if lvl is not None and lvl.get(f"{{{W}}}val", "").isdigit():
            n = int(lvl.get(f"{{{W}}}val"))
            if n < 9:
                return n + 1
    if style_el is not None:
        m = _STYLE_NAME.match(style_el.name or "")
        if m:
            return int(m.group(1))
        if _TOC_HEADING.match(style_el.name or ""):
            return 1  # the table of contents' own title: a level-1 section without outline level
        lvl = style_el.element.find(f"{{{W}}}pPr/{{{W}}}outlineLvl")
        if lvl is not None and lvl.get(f"{{{W}}}val", "").isdigit():
            n = int(lvl.get(f"{{{W}}}val"))
            if n < 9:
                return n + 1
    return None


def extract_docx(path) -> list[dict]:
    import docx

    document = docx.Document(str(path))
    styles = {s.style_id: s for s in document.styles}
    result = []
    for i, p in enumerate(iter_body_paragraphs(document)):
        ppr = p.find(f"{{{W}}}pPr")
        sid = None if ppr is None else ppr.find(f"{{{W}}}pStyle")
        style = styles.get(sid.get(f"{{{W}}}val")) if sid is not None else None
        result.append({
            "id": i,
            "style": style.name if style is not None else "Normal",
            "heading_level": _heading_level(p, styles),
            "text": visible_text(p),
        })
    return result


_INPUT = re.compile(r"^\\(?:input|include)\s*\{([^}]*)\}\s*(?:%.*)?$")


_TEX_LINE = re.compile(r"[^\r\n]*(?:\r\n|\n|\r)|[^\r\n]+")


def split_tex_lines(text: str) -> list[str]:
    """Lines of a .tex text, terminators kept; only \\r\\n, \\n and \\r end a line.

    (str.splitlines also splits on form feed and others, which editors do not count.)
    """
    return _TEX_LINE.findall(text)


def read_tex_text(path: Path) -> tuple[str, bool]:
    """(text, is_latin1) of a .tex file.

    UTF-8 is lossless: stray invalid bytes survive as lone surrogates (re-encode with
    errors="surrogateescape"). A file with invalid bytes and no valid non-ASCII UTF-8 at
    all is read as latin-1 instead.
    """
    text = Path(path).read_bytes().decode("utf-8", errors="surrogateescape")
    bad = sum(1 for c in text if "\udc80" <= c <= "\udcff")
    if bad and not any(ord(c) > 127 and not "\udc80" <= c <= "\udcff" for c in text):
        return Path(path).read_bytes().decode("latin-1"), True
    return text, False


def extract_tex(main: Path) -> list[dict]:
    main = Path(main)
    base = main.parent
    result = []
    seen = set()

    def read(file: Path):
        key = file.resolve()
        if key in seen or not file.is_file():
            return
        seen.add(key)
        rel = file.relative_to(base).as_posix() if file.is_relative_to(base) else file.name
        text = read_tex_text(file)[0].encode("utf-8", "surrogateescape").decode("utf-8", "replace")
        lines = split_tex_lines(text)
        for n, raw in enumerate(lines, start=1):
            line = raw.strip()
            if not line or line.startswith("%"):
                continue
            m = _INPUT.match(line)
            if m:
                name = m.group(1).strip()
                if not name.endswith(".tex"):
                    name += ".tex"
                read(base / name)
                continue
            result.append({"id": len(result), "file": rel, "line": n, "text": line})
        seen.discard(key)

    read(main)
    return result


def extract_pdf(path) -> list[dict]:
    """One paragraph per block of lines; a block ends at a vertical gap clearly
    larger than the page's typical line pitch (pdfplumber emits no blank lines)."""
    import statistics

    import pdfplumber

    result = []
    with pdfplumber.open(str(path)) as pdf:
        for number, page in enumerate(pdf.pages, start=1):
            lines = page.extract_text_lines()
            pitches = [b["top"] - a["top"] for a, b in zip(lines, lines[1:])
                       if b["top"] > a["top"]]
            typical = statistics.median(pitches) if pitches else 0
            block, prev = [], None
            for line in lines + [None]:
                gap = (line["top"] - prev["top"]) if (line and prev) else 0
                if block and (line is None or (typical and gap > 1.3 * typical)):
                    text = " ".join(" ".join(block).split())
                    if text:
                        result.append({"id": len(result), "page": number, "text": text})
                    block = []
                if line is not None:
                    block.append(line["text"])
                    prev = line
    return result


_FORMATS = {".docx": "docx", ".tex": "latex", ".pdf": "pdf"}


def extract(path) -> dict:
    path = Path(path)
    fmt = _FORMATS.get(path.suffix.lower())
    if fmt is None:
        raise ValueError(f"unsupported format '{path.suffix}' (use .docx, .tex or .pdf)")
    paragraphs = {"docx": extract_docx, "latex": extract_tex, "pdf": extract_pdf}[fmt](path)
    return {"format": fmt, "source": str(path), "paragraphs": paragraphs}


def add_arguments(parser):
    parser.add_argument("document", help="document to read (.docx, .tex, .pdf)")


def run(args) -> int:
    path = Path(args.document)
    if not path.is_file():
        print(f"error: file not found: {path}", file=sys.stderr)
        return 2
    if cli.refuses_overwrite(path, args):
        return 2
    try:
        data = extract(path)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # corrupt or unreadable document
        print(f"error: cannot read {path.name} as a valid document "
              f"({type(exc).__name__}: {exc})", file=sys.stderr)
        return 2
    text = "\n".join(f"[{p['id']}] {p['text']}" for p in data["paragraphs"])
    cli.emit(data, args, text=text)
    return 0
