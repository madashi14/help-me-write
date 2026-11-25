"""Assemble a .docx from the Markdown sources of the chapters (the Word branch of writing).

The chapter format is described for the writer in skills/scrittura-capitolo/
formato-capitoli.md: headings `#`-`###`, paragraphs, `- ` and `1. ` lists, **bold**,
*italic*, `code`, figures `![Caption](file.png){#fig:x width=12cm}`, pipe tables under
`Tabella: Caption {#tab:x}`, references `@fig:x` / `@tab:x`, citations `[@key]` /
`[@a; @b]`, placeholders `[DA VERIFICARE: ...]`. Paths in the manifest are relative to its
folder; image paths are relative to the chapter file.

Construction order (the page layout is fixed before the numbers of the table of contents):
1. validation of the manifest and of every chapter (all problems are reported together);
2. base: a copy of the title page, followed by a next-page section break, or an empty
   document; the title page has no header or footer (titlePg), the following pages are
   numbered by the footer apply_layout adds;
3. table of contents: a "TOC Heading" paragraph and a TOC field with one entry per heading
   (TOC 1-3, right tab with dot leader) and the provisional page number 00;
4. content: headings (Heading 1-3, a level-1 heading starts a new page), figures and their
   "Caption" paragraphs with a SEQ field, tables with the caption above, and at the end the
   bibliography: the cited entries in order of first citation;
5. layout: apply_layout; then the title page is put back as it was in the model (its
   paragraphs, the page geometry of its section and frozen copies of its styles), because
   apply_layout protects only a title page of at most 15 paragraphs;
6. table of contents numbers: the document is rendered with LibreOffice, each heading is
   located with measure.section_spans and its 00 is replaced by the number printed on that
   page (physical page minus the offset read from the page numbers of the footers); the
   entries are not regenerated, so the pages do not move. Without LibreOffice the 00 stay,
   with a warning; Word recomputes the table when the document is opened (updateFields).
"""
import copy
import re
import shutil
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from lxml import etree

from .layout import LayoutError, apply_layout, load_layout
from .render import RenderError, render_pdf

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
XML_NS = "http://www.w3.org/XML/1998/namespace"
CM_PER_INCH = 2.54
PT_PER_CM = 72 / 2.54
MAX_FIGURE_HEIGHT_SHARE = 0.8  # of the text height: room is left for the caption
TOC_PLACEHOLDER = "00"         # two digits: real numbers below 100 are never wider
NO_TOC_NUMBERS = "table of contents without page numbers: update it in Word (F9)"

KNOWN_KEYS = ("title_page", "layout", "chapters", "bibliography", "language", "toc",
              "toc_title", "bibliography_title")
_WORDS = {
    "it": {"figure": "Figura", "table": "Tabella", "toc": "Indice", "bibliography": "Bibliografia"},
    "en": {"figure": "Figure", "table": "Table", "toc": "Contents", "bibliography": "References"},
}


def _q(tag: str) -> str:
    return f"{{{W}}}{tag}"


class AssembleError(Exception):
    """The manifest or the chapters are not usable; problems lists every reason."""

    def __init__(self, problems):
        super().__init__("; ".join(problems))
        self.problems = list(problems)


# --- chapter sources -----------------------------------------------------------------------

@dataclass
class Heading:
    level: int
    text: str
    line: int = 0


@dataclass
class Paragraph:
    text: str
    line: int = 0


@dataclass
class ListBlock:
    ordered: bool
    items: list[str]
    line: int = 0


@dataclass
class Figure:
    caption: str
    path: str
    label: str | None = None
    width_cm: float | None = None
    width_percent: float | None = None
    line: int = 0


@dataclass
class Table:
    caption: str | None
    label: str | None
    header: list[str]
    rows: list[list[str]]
    align: list[str] = field(default_factory=list)  # "left", "center" or "right" per column
    line: int = 0


_HEADING_RE = re.compile(r"^(#+)[ \t]+(.*?)(?:[ \t]+#+)?[ \t]*$")
_FIGURE_RE = re.compile(r"^!\[(?P<caption>.*)\]\((?P<path>[^()]*)\)[ \t]*(?:\{(?P<attrs>[^{}]*)\})?$")
_TABLE_CAPTION_RE = re.compile(
    r"^(?:Tabella|Table)[ \t]*:[ \t]*(?P<caption>.*?)[ \t]*(?:\{(?P<attrs>[^{}]*)\})?$")
_BULLET_RE = re.compile(r"^[-*+][ \t]+(.*)$")
_ORDERED_RE = re.compile(r"^(\d{1,9})[.)][ \t]+(.*)$")
_SEPARATOR_CELL_RE = re.compile(r"^:?-+:?$")
_LABEL_RE = re.compile(r"^(fig|tab):[\w-]+$")
_WIDTH_RE = re.compile(r"^(\d+(?:[.,]\d+)?)(cm|mm|in|pt|%)$")
_CM_PER_UNIT = {"cm": 1.0, "mm": 0.1, "in": CM_PER_INCH, "pt": 1 / PT_PER_CM}


def _list_marker(line: str):
    """("bullet"|"ordered", text, number) for a list item line, else None."""
    m = _BULLET_RE.match(line)
    if m:
        return "bullet", m.group(1).strip(), None
    m = _ORDERED_RE.match(line)
    if m:
        return "ordered", m.group(2).strip(), int(m.group(1))
    return None


def _cells(row: str) -> list[str]:
    s = row.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", s)]


def _attributes(text, kind, line, problems):
    """(label, width_cm, width_percent) from `#fig:x width=12cm`; problems for the rest."""
    label = width_cm = width_percent = None
    for token in (text or "").split():
        if token.startswith("#"):
            label = token[1:]
            if not _LABEL_RE.match(label) or not label.startswith(kind + ":"):
                problems.append((line, f"label '{label}' must be {kind}:<name> (letters, digits, "
                                       "- and _)"))
                label = None
        elif token.startswith("width=") and kind == "fig":
            m = _WIDTH_RE.match(token[len("width="):].strip().lower())
            if m is None:
                problems.append((line, f"width '{token[6:]}' not understood: write e.g. "
                                       "width=12cm, width=80mm or width=50%"))
                continue
            value = float(m.group(1).replace(",", "."))
            if m.group(2) == "%":
                width_percent = value
            else:
                width_cm = round(value * _CM_PER_UNIT[m.group(2)], 4)
            if value <= 0:
                problems.append((line, f"width '{token[6:]}' must be greater than 0"))
        else:
            problems.append((line, f"unknown attribute '{token}' (use #{kind}:<name>"
                                   + (" and width=…" if kind == "fig" else "") + ")"))
    return label, width_cm, width_percent


def _starts_block(lines, i) -> bool:
    """True if line i starts a block that interrupts a paragraph."""
    s = lines[i].strip()
    if s.startswith(("#", "```", "~~~", "|")) and (not s.startswith("#") or _HEADING_RE.match(s)):
        return True
    if _FIGURE_RE.match(s):
        return True
    marker = _list_marker(s)
    if marker and (marker[0] == "bullet" or marker[2] == 1):
        return True
    m = _TABLE_CAPTION_RE.match(s)
    return bool(m and m.group("attrs"))


def _parse(text: str):
    """(blocks, problems) of a chapter source; problems are (line, message)."""
    lines = text.splitlines()
    blocks, problems = [], []
    i, n = 0, len(lines)
    while i < n:
        raw = lines[i]
        s = raw.strip()
        line = i + 1
        if not s:
            i += 1
            continue
        if s.startswith(("```", "~~~")):
            fence = s[:3]
            problems.append((line, "code blocks are not supported: write the code inline "
                                   "with `backticks` or describe it in the text"))
            i += 1
            while i < n and not lines[i].strip().startswith(fence):
                i += 1
            i += 1
            continue
        m = _HEADING_RE.match(s)
        if m:
            level = len(m.group(1))
            if level > 3:
                problems.append((line, f"heading '{'#' * level} {m.group(2)}': only #, ## and "
                                       "### are supported"))
            else:
                blocks.append(Heading(level, m.group(2).strip(), line))
            i += 1
            continue
        m = _FIGURE_RE.match(s)
        if m:
            label, width_cm, width_percent = _attributes(m.group("attrs"), "fig", line, problems)
            path = m.group("path").strip()
            if path.startswith("<") and path.endswith(">"):
                path = path[1:-1].strip()
            if not path:
                problems.append((line, "figure without an image path"))
            blocks.append(Figure(m.group("caption").strip(), path, label, width_cm,
                                 width_percent, line))
            i += 1
            continue
        caption = _TABLE_CAPTION_RE.match(s)
        if caption or s.startswith("|"):
            j = i + 1 if caption else i
            while caption and j < n and not lines[j].strip():
                j += 1
            if caption and not (j < n and lines[j].strip().startswith("|")):
                if caption.group("attrs"):
                    problems.append((line, "a table caption must be followed by a pipe table "
                                           "(| a | b |)"))
                    i += 1
                    continue
            else:
                i = _parse_table(lines, j, caption, line, blocks, problems)
                continue
        marker = _list_marker(s)
        if marker:
            i = _parse_list(lines, i, marker[0], blocks, problems)
            continue
        parts, start = [], i
        while i < n and lines[i].strip() and (i == start or not _starts_block(lines, i)):
            parts.append(lines[i].strip())
            i += 1
        blocks.append(Paragraph(" ".join(parts), line))
    return blocks, problems


def _parse_table(lines, i, caption, caption_line, blocks, problems) -> int:
    rows = []
    while i < len(lines) and lines[i].strip().startswith("|"):
        rows.append((i + 1, lines[i].strip()))
        i += 1
    line = caption_line if caption else rows[0][0]
    separator = _cells(rows[1][1]) if len(rows) > 1 else []
    if len(rows) < 2 or not all(_SEPARATOR_CELL_RE.match(c.replace(" ", "")) for c in separator):
        problems.append((rows[0][0], "a table needs a header row, a separator row "
                                     "(|---|---|) and then the data rows"))
        return i
    header = _cells(rows[0][1])
    if len(separator) != len(header):
        problems.append((rows[1][0], f"the separator row has {len(separator)} cell(s), the "
                                     f"header has {len(header)}"))
    align = []
    for c in separator + ["-"] * (len(header) - len(separator)):
        c = c.replace(" ", "")
        align.append("center" if c.startswith(":") and c.endswith(":") and len(c) > 1
                     else "right" if c.endswith(":") else "left")
    data = []
    for row_line, row in rows[2:]:
        cells = _cells(row)
        if len(cells) != len(header):
            problems.append((row_line, f"table row has {len(cells)} cell"
                                       f"{'s' if len(cells) != 1 else ''}, the header has "
                                       f"{len(header)}"))
        data.append((cells + [""] * len(header))[:len(header)])
    label = None
    text = None
    if caption:
        text = caption.group("caption").strip()
        label = _attributes(caption.group("attrs"), "tab", caption_line, problems)[0]
    blocks.append(Table(text, label, header, data, align[:len(header)], line))
    return i


def _indent(raw: str) -> int:
    return len(raw) - len(raw.lstrip())


def _parse_list(lines, i, kind, blocks, problems) -> int:
    items, line, n = [], i + 1, len(lines)
    base = _indent(lines[i])  # items at this indentation; deeper lines continue an item
    while i < n:
        raw = lines[i]
        s = raw.strip()
        marker = _list_marker(s)
        indented = _indent(raw) > base
        if not s:
            j = i
            while j < n and not lines[j].strip():
                j += 1
            following = _list_marker(lines[j].strip()) if j < n else None
            if following and following[0] == kind and _indent(lines[j]) <= base:
                i = j
                continue
            break
        if marker and not indented:
            if marker[0] != kind:
                break
            items.append(marker[1])
        elif marker and indented:
            problems.append((i + 1, "nested lists are not supported: use a single level"))
            items.append(marker[1])
        elif not indented and _starts_block(lines, i):
            break
        else:
            items[-1] = f"{items[-1]} {s}"
        i += 1
    blocks.append(ListBlock(kind == "ordered", items, line))
    return i


def parse_chapter(text: str, problems: list | None = None) -> list:
    """The blocks of a chapter source (Heading, Paragraph, ListBlock, Figure, Table).

    With a problems list, problems are appended to it as (line, message); without, they
    raise AssembleError.
    """
    blocks, found = _parse(text)
    if problems is not None:
        problems.extend(found)
    elif found:
        raise AssembleError([f"line {line}: {message}" for line, message in found])
    return blocks


# --- inline text ---------------------------------------------------------------------------

@dataclass
class _Token:
    kind: str           # "text", "code", "todo", "cite", "ref" or "delim" (an emphasis run)
    value: object       # str; list of keys for "cite"
    bold: bool = False
    italic: bool = False


_INLINE_RE = re.compile(r"\\[\\`*_{}\[\]()#+\-.!|@~]|`+|\[DA VERIFICARE:|\[@"
                        r"|(?<![\w@])@(?:fig|tab):[\w-]+|\*+")
_CITE_KEY_RE = re.compile(r"^@([^\s;,\[\]@]+)$")


def _closing_bracket(text: str, start: int) -> int:
    """Index of the ] closing the [ at start (nested brackets balanced), or -1."""
    depth = 0
    for k in range(start, len(text)):
        if text[k] == "[":
            depth += 1
        elif text[k] == "]":
            depth -= 1
            if depth == 0:
                return k
    return -1


def _tokens(text: str, problems=None) -> list[_Token]:
    """Inline tokens of a text with bold/italic resolved; problems (messages) are appended
    for citations written in an unsupported form."""
    out, pos = [], 0

    def literal(s):
        if out and out[-1].kind == "text":
            out[-1].value += s
        elif s:
            out.append(_Token("text", s))

    while True:
        m = _INLINE_RE.search(text, pos)
        if m is None:
            literal(text[pos:])
            break
        literal(text[pos:m.start()])
        tok = m.group(0)
        pos = m.end()
        if tok.startswith("\\"):
            literal(tok[1:])
        elif tok.startswith("`"):
            close = re.compile(r"(?<!`)" + tok + r"(?!`)").search(text, pos)
            if close is None:
                literal(tok)
            else:
                code = text[pos:close.start()]
                if len(code) > 2 and code[0] == code[-1] == " " and code.strip():
                    code = code[1:-1]
                out.append(_Token("code", code))
                pos = close.end()
        elif tok == "[DA VERIFICARE:":
            end = _closing_bracket(text, m.start())
            if end < 0:
                literal(tok)
            else:
                out.append(_Token("todo", text[m.start():end + 1]))
                pos = end + 1
        elif tok == "[@":
            end = text.find("]", m.start())
            parts = [p.strip() for p in text[m.start() + 1:end].split(";")] if end > 0 else []
            keys = [_CITE_KEY_RE.match(p) for p in parts]
            if end > 0 and keys and all(keys):
                out.append(_Token("cite", [k.group(1) for k in keys]))
                pos = end + 1
            else:
                shown = text[m.start():end + 1] if end > 0 else text[m.start():m.start() + 30]
                if problems is not None:
                    problems.append(f"unsupported citation '{shown}': write [@key] or "
                                    "[@key1; @key2] (no page numbers or other text inside)")
                literal(tok)
        elif tok.startswith("@"):
            out.append(_Token("ref", tok[1:]))
        else:  # a run of *
            before = text[m.start() - 1] if m.start() > 0 else " "
            after = text[m.end()] if m.end() < len(text) else " "
            out.append(_Token("delim", tok, bold=not after.isspace(),   # bold/italic: can open
                              italic=not before.isspace()))             # / can close
    return _emphasis(out)


def _emphasis(tokens: list[_Token]) -> list[_Token]:
    """Pair * / ** / *** runs (an opener with the next closer of the same length); unpaired
    runs stay literal."""
    stack, pairs = [], []
    for i, t in enumerate(tokens):
        if t.kind != "delim":
            continue
        can_open, can_close = t.bold, t.italic
        if can_close:
            k = next((k for k in range(len(stack) - 1, -1, -1)
                      if tokens[stack[k]].value == t.value), None)
            if k is not None and len(t.value) <= 3:
                pairs.append((stack[k], i, len(t.value)))
                del stack[k:]
                continue
        if can_open:
            stack.append(i)
    result = [_Token(t.kind, t.value) for t in tokens]
    for start, end, count in pairs:
        result[start] = result[end] = None
    for start, end, count in pairs:
        for t in result[start + 1:end]:
            if t is not None:
                t.bold = t.bold or count >= 2
                t.italic = t.italic or count in (1, 3)
    merged = []
    for t in result:
        if t is None:
            continue
        if t.kind == "delim":
            t.kind = "text"
        if merged and t.kind == "text" and merged[-1].kind == "text" and \
                (merged[-1].bold, merged[-1].italic) == (t.bold, t.italic):
            merged[-1].value += t.value
        else:
            merged.append(t)
    return merged


def _inline_texts(block):
    """The inline texts of a block, in reading order."""
    if isinstance(block, (Heading, Paragraph)):
        yield block.text
    elif isinstance(block, ListBlock):
        yield from block.items
    elif isinstance(block, Figure):
        yield block.caption
    elif isinstance(block, Table):
        if block.caption:
            yield block.caption
        yield from block.header
        for row in block.rows:
            yield from row


# --- manifest ------------------------------------------------------------------------------

@dataclass
class _Chapter:
    path: Path
    name: str
    blocks: list


@dataclass
class _Project:
    folder: Path
    layout: object
    chapters: list[_Chapter]
    title_page: Path | None = None
    entries: dict = field(default_factory=dict)
    bibliography: Path | None = None
    language: str = "it"
    toc: bool = True
    toc_title: str = "Indice"
    bibliography_title: str = "Bibliografia"

    @property
    def words(self) -> dict:
        return _WORDS[self.language]


def _resolve(folder: Path, value) -> Path:
    return (folder / str(value)).resolve() if not Path(str(value)).is_absolute() else Path(value)


def _image_problem(path: Path) -> str | None:
    if not path.is_file():
        return f"image not found: {path}"
    try:
        from docx.image.image import Image

        Image.from_file(str(path))
    except Exception:
        return (f"image {path.name} cannot be read or is not in a supported format "
                "(use PNG or JPEG)")
    return None


def _load(manifest) -> tuple[_Project | None, list[str]]:
    """The project of a manifest and every problem found (the project is None with any)."""
    import yaml

    manifest = Path(manifest)
    if not manifest.is_file():
        return None, [f"manifest not found: {manifest}"]
    try:
        data = yaml.safe_load(manifest.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        return None, [f"cannot read {manifest}: {exc}"]
    if not isinstance(data, dict):
        return None, [f"{manifest.name} must be a YAML mapping (key: value lines)"]
    problems = []
    folder = manifest.parent.resolve()
    for key in data:
        if key not in KNOWN_KEYS:
            problems.append(f"unknown key '{key}' in {manifest.name} (known keys: "
                            f"{', '.join(KNOWN_KEYS)})")
    language = data.get("language", "it")
    if language not in _WORDS:
        problems.append(f"language must be 'it' or 'en', not {language!r}")
        language = "it"
    toc = data.get("toc", True)
    if not isinstance(toc, bool):
        problems.append(f"toc must be true or false, not {toc!r}")
    titles = {}
    for key, default in (("toc_title", _WORDS[language]["toc"]),
                         ("bibliography_title", _WORDS[language]["bibliography"])):
        value = data.get(key, default)
        if not isinstance(value, str) or not value.strip():
            problems.append(f"{key} must be a non-empty text")
            value = default
        titles[key] = " ".join(value.split())

    layout = None
    if data.get("layout") in (None, ""):
        problems.append("layout is required: the JSON file written by `hmw layout` "
                        "(relative to the manifest's folder)")
    else:
        path = _resolve(folder, data["layout"])
        if not path.is_file():
            problems.append(f"layout file not found: {path}")
        else:
            try:
                layout = load_layout(path)
            except LayoutError as exc:
                problems.append(str(exc))

    title_page = None
    if data.get("title_page") not in (None, ""):
        title_page = _resolve(folder, data["title_page"])
        if not title_page.is_file():
            problems.append(f"title page not found: {title_page}")
        elif title_page.suffix.lower() != ".docx":
            problems.append(f"title page must be a .docx file: {title_page.name}")
        else:
            try:
                import docx

                docx.Document(str(title_page))
            except Exception as exc:
                problems.append(f"title page {title_page.name} is not a readable .docx "
                                f"({type(exc).__name__}: {exc})")

    entries, bibliography = None, None
    if data.get("bibliography") not in (None, ""):
        bibliography = _resolve(folder, data["bibliography"])
        if not bibliography.is_file():
            problems.append(f"bibliography not found: {bibliography}")
        else:
            from .bib import BibError, bibtex_entries

            try:
                entries = {e.key: e for e in bibtex_entries(bibliography)}
            except BibError as exc:
                problems.append(str(exc))

    chapters = []
    listed = data.get("chapters")
    if not isinstance(listed, list) or not listed:
        problems.append("chapters is required: the list of chapter files, in order "
                        "(relative to the manifest's folder)")
        listed = []
    for item in listed:
        if not isinstance(item, str) or not item.strip():
            problems.append(f"chapters: {item!r} is not a file name")
            continue
        path = _resolve(folder, item)
        try:
            text = path.read_text(encoding="utf-8-sig")
        except FileNotFoundError:
            problems.append(f"chapter not found: {path}")
            continue
        except (OSError, UnicodeDecodeError) as exc:
            problems.append(f"cannot read chapter {path}: {exc}")
            continue
        found = []
        blocks = parse_chapter(text, found)
        problems += [f"{item}:{line}: {message}" for line, message in found]
        chapters.append(_Chapter(path, item, blocks))

    problems += _check_references(chapters, entries, bibliography)
    if problems:
        return None, problems
    return _Project(folder, layout, chapters, title_page, entries or {}, bibliography,
                    language, toc, titles["toc_title"], titles["bibliography_title"]), []


def _check_references(chapters, entries, bibliography) -> list[str]:
    """Images, labels (unique, all defined), citations (keys in the .bib), inline syntax."""
    problems, defined, refs = [], {}, []
    for chapter in chapters:
        for block in chapter.blocks:
            where = f"{chapter.name}:{block.line}"
            if isinstance(block, Figure) and block.path:
                problem = _image_problem(_resolve(chapter.path.parent, block.path))
                if problem:
                    problems.append(f"{where}: {problem}")
            label = getattr(block, "label", None)
            if label:
                if label in defined:
                    problems.append(f"{where}: label {label} is already used at {defined[label]}")
                else:
                    defined[label] = where
            for text in _inline_texts(block):
                found = []
                tokens = _tokens(text, found)
                problems += [f"{where}: {message}" for message in found]
                if isinstance(block, Paragraph) and re.search(r"!\[[^\]]*\]\(", text):
                    problems.append(f"{where}: a figure must be alone on its line, with a "
                                    "blank line before and after it")
                for t in tokens:
                    if t.kind == "ref":
                        refs.append((where, t.value))
                    elif t.kind == "cite" and (entries is not None or bibliography is None):
                        for key in t.value:  # (an unreadable .bib is reported by itself)
                            if entries is None:
                                problems.append(f"{where}: [@{key}] needs a bibliography (.bib) "
                                                "in the manifest")
                            elif key not in entries:
                                problems.append(f"{where}: citation key '{key}' is not in "
                                                f"{bibliography.name}")
    for where, label in refs:
        if label not in defined:
            problems.append(f"{where}: @{label} refers to no figure or table "
                            f"(define it with {{#{label}}})")
    return problems


def validate_manifest(path: Path) -> list[str]:
    """Every problem of the manifest and of its chapters; an empty list when usable."""
    return _load(Path(path))[1]


# --- building the document -----------------------------------------------------------------

def _nsdecl() -> str:
    return f'xmlns:w="{W}"'


def _style_definitions(normal: str | None, heading1: str) -> dict:
    """key -> (type, styleId, name, XML) of the styles the document needs."""
    based = f'<w:basedOn w:val="{normal}"/><w:next w:val="{normal}"/>' if normal else ""

    def paragraph(sid, name, inner, base=None, priority=None):
        head = (f'<w:basedOn w:val="{base}"/><w:next w:val="{normal}"/>' if base and normal
                else based)
        prio = f'<w:uiPriority w:val="{priority}"/><w:unhideWhenUsed/>' if priority else ""
        return ("paragraph", sid, name,
                f'<w:style {_nsdecl()} w:type="paragraph" w:styleId="{sid}"><w:name w:val="{name}"/>'
                f'{head}{prio}<w:qFormat/>{inner}</w:style>')

    def toc(level):
        indent = f'<w:ind w:left="{(level - 1) * 284}"/>' if level > 1 else ""
        return paragraph(f"TOC{level}", f"toc {level}",
                         f'<w:pPr><w:spacing w:before="0" w:after="0"/>{indent}</w:pPr>',
                         priority=39)

    border = 'w:val="single" w:sz="4" w:space="0" w:color="auto"'
    return {
        "heading1": paragraph("Heading1", "heading 1",
                              '<w:pPr><w:keepNext/><w:keepLines/><w:spacing w:before="0" '
                              'w:after="240"/><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:b/>'
                              '<w:bCs/><w:sz w:val="32"/><w:szCs w:val="32"/></w:rPr>', priority=9),
        "heading2": paragraph("Heading2", "heading 2",
                              '<w:pPr><w:keepNext/><w:keepLines/><w:spacing w:before="240" '
                              'w:after="120"/><w:outlineLvl w:val="1"/></w:pPr><w:rPr><w:b/>'
                              '<w:bCs/><w:sz w:val="28"/><w:szCs w:val="28"/></w:rPr>', priority=9),
        "heading3": paragraph("Heading3", "heading 3",
                              '<w:pPr><w:keepNext/><w:keepLines/><w:spacing w:before="240" '
                              'w:after="120"/><w:outlineLvl w:val="2"/></w:pPr><w:rPr><w:b/>'
                              '<w:bCs/><w:i/><w:iCs/><w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr>',
                              priority=9),
        # based on Heading 1 for its look, outline level 9 = body text: not in the TOC itself
        "toc_heading": paragraph("TOCHeading", "TOC Heading",
                                 '<w:pPr><w:outlineLvl w:val="9"/></w:pPr><w:rPr><w:b/><w:bCs/>'
                                 '</w:rPr>', base=heading1, priority=39),
        "toc1": toc(1), "toc2": toc(2), "toc3": toc(3),
        "caption": paragraph("Caption", "caption",
                             '<w:pPr><w:spacing w:before="0" w:after="120"/><w:jc w:val="center"/>'
                             '</w:pPr><w:rPr><w:i/><w:iCs/></w:rPr>', priority=35),
        "table": ("table", "TableGrid", "Table Grid",
                  f'<w:style {_nsdecl()} w:type="table" w:styleId="TableGrid"><w:name '
                  'w:val="Table Grid"/><w:uiPriority w:val="59"/><w:tblPr><w:tblBorders>'
                  + "".join(f"<w:{side} {border}/>" for side in
                            ("top", "left", "bottom", "right", "insideH", "insideV"))
                  + '</w:tblBorders><w:tblCellMar><w:left w:w="108" w:type="dxa"/><w:right '
                  'w:w="108" w:type="dxa"/></w:tblCellMar></w:tblPr></w:style>'),
        "code": ("character", "HTMLCode", "HTML Code",
                 f'<w:style {_nsdecl()} w:type="character" w:styleId="HTMLCode"><w:name '
                 'w:val="HTML Code"/><w:uiPriority w:val="99"/><w:unhideWhenUsed/><w:rPr>'
                 '<w:rFonts w:ascii="Courier New" w:hAnsi="Courier New" w:cs="Courier New"/>'
                 '</w:rPr></w:style>'),
    }


def _style_elements(styles_el):
    return [s for s in styles_el.findall(_q("style"))]


def _style_name(style_el) -> str:
    name = style_el.find(_q("name"))
    return (name.get(_q("val")) if name is not None else "") or ""


def _ensure_styles(document, own: bool) -> dict:
    """key -> styleId of the styles the content uses, created when missing.

    own (an empty base document): python-docx's defaults are replaced by these definitions,
    so the look does not depend on its template. Otherwise the model's styles, found by
    name (case-insensitive), are kept as they are.
    """
    from docx.oxml import parse_xml

    styles_el = document.styles.element
    normal = next((s.get(_q("styleId")) for s in _style_elements(styles_el)
                   if s.get(_q("type")) == "paragraph" and s.get(_q("default")) in ("1", "true", "on")),
                  None)
    by_name = {}
    for s in _style_elements(styles_el):
        by_name.setdefault((s.get(_q("type")), _style_name(s).lower()), s)
    heading1 = by_name.get(("paragraph", "heading 1"))
    heading1_id = heading1.get(_q("styleId")) if heading1 is not None and not own else "Heading1"
    definitions = _style_definitions(normal, heading1_id)
    ids = {}
    for key, (kind, sid, name, xml) in definitions.items():
        existing = by_name.get((kind, name.lower()))
        if existing is not None and own:
            styles_el.remove(existing)
            existing = None
        if existing is not None:
            ids[key] = existing.get(_q("styleId"))
            continue
        taken = {s.get(_q("styleId")) for s in _style_elements(styles_el)}
        new_id, n = sid, 2
        while new_id in taken:
            new_id, n = f"{sid}{n}", n + 1
        element = parse_xml(xml.replace(f'w:styleId="{sid}"', f'w:styleId="{new_id}"'))
        styles_el.append(element)
        ids[key] = new_id
        if key == "heading1" and new_id != heading1_id:
            heading1_id = new_id
            toc_heading = definitions["toc_heading"]
            definitions["toc_heading"] = toc_heading[:3] + (
                toc_heading[3].replace('w:basedOn w:val="Heading1"', f'w:basedOn w:val="{new_id}"'),)
    return ids


def _set_update_fields(document) -> None:
    """w:updateFields true in settings.xml (Word recomputes the TOC when opening)."""
    from docx.oxml import OxmlElement

    settings = document.settings.element
    existing = settings.find(_q("updateFields"))
    if existing is not None:
        existing.set(_q("val"), "true")
        return
    element = OxmlElement("w:updateFields")
    element.set(_q("val"), "true")
    later = ("hdrShapeDefaults", "footnotePr", "endnotePr", "compat", "docVars", "rsids")
    anchor = next((c for c in settings if not isinstance(c.tag, str) or not c.tag.startswith(f"{{{W}}}")
                   or etree.QName(c).localname in later), None)
    if anchor is None:
        settings.append(element)
    else:
        anchor.addprevious(element)


def _drop_trailing_page_break(p) -> None:
    """Remove a page break after the last text of p (it would leave an empty page)."""
    breaks = [br for br in p.iter(_q("br")) if br.get(_q("type")) == "page"]
    if not breaks:
        return
    last = breaks[-1]
    after = False
    for node in p.iter():
        if node is last:
            after = True
        elif after and node.tag == _q("t") and (node.text or "").strip():
            return
    run = last.getparent()
    run.remove(last)
    if not len([c for c in run if c.tag != _q("rPr")]):
        run.getparent().remove(run)


@dataclass
class _TocEntry:
    level: int
    text: str
    bookmark: str


class _Builder:
    def __init__(self, project: _Project):
        self.project = project
        self.words = project.words
        self.warnings: list[str] = []
        self.figure_numbers: dict[str, int] = {}
        self.table_numbers: dict[str, int] = {}
        self.citation_numbers: dict[str, int] = {}
        self.figures = self.tables = self.placeholders = 0
        self._number()
        m = project.layout.margins_cm
        self.text_width_cm = project.layout.paper_cm[0] - m["left"] - m["right"]
        self.text_height_cm = project.layout.paper_cm[1] - m["top"] - m["bottom"]
        self.document = None
        self.styles = {}
        self.title_count = 0
        self.toc_entries: list[_TocEntry] = []
        self._bookmark_id = 0
        self._numbering = None
        self._at_page_start = True
        self._after_table = False

    # numbers -------------------------------------------------------------------------------

    def _number(self):
        referenced = set()
        for chapter in self.project.chapters:
            for block in chapter.blocks:
                if isinstance(block, Figure):
                    self.figures += 1
                    if block.label:
                        self.figure_numbers[block.label] = self.figures
                elif isinstance(block, Table) and block.caption is not None:
                    self.tables += 1
                    if block.label:
                        self.table_numbers[block.label] = self.tables
                for text in _inline_texts(block):
                    for t in _tokens(text):
                        if t.kind == "cite":
                            for key in t.value:
                                self.citation_numbers.setdefault(key, len(self.citation_numbers) + 1)
                        elif t.kind == "ref":
                            referenced.add(t.value)
                        elif t.kind == "todo":
                            self.placeholders += 1
        figure = self.words["figure"]
        n = 0
        for chapter in self.project.chapters:
            for block in chapter.blocks:
                where = f"{chapter.name}:{block.line}"
                if isinstance(block, Figure):
                    n += 1
                    if not block.label:
                        self.warnings.append(f"{figure} {n} ({where}) has no label: the text "
                                             "cannot refer to it (add {#fig:<name>})")
                    elif block.label not in referenced:
                        self.warnings.append(f"{figure} {n} ({where}) is never referenced in the "
                                             f"text (@{block.label})")
                elif isinstance(block, Table) and block.caption is None:
                    self.warnings.append(f"table at {where} has no caption: it is not numbered "
                                         "(write 'Tabella: Caption {#tab:<name>}' above it)")
        if self.placeholders:
            self.warnings.append(f"{self.placeholders} [DA VERIFICARE: …] placeholder(s) in the "
                                 "text: they are highlighted in yellow and must be resolved")

    def token_text(self, t: _Token) -> str:
        if t.kind == "cite":
            numbers = sorted({self.citation_numbers[k] for k in t.value})
            return "[" + ", ".join(str(n) for n in numbers) + "]"
        if t.kind == "ref":
            if t.value.startswith("fig:"):
                return f"{self.words['figure']} {self.figure_numbers[t.value]}"
            return f"{self.words['table']} {self.table_numbers[t.value]}"
        return t.value

    def plain(self, text: str) -> str:
        return "".join(self.token_text(t) for t in _tokens(text))

    # base ----------------------------------------------------------------------------------

    def base(self):
        import docx

        project = self.project
        if project.title_page is None:
            self.document = docx.Document()
            self._set_language()
        else:
            self.document = docx.Document(str(project.title_page))
            self._after_title_page()
        self.styles = _ensure_styles(self.document, own=project.title_page is None)
        _set_update_fields(self.document)
        ids = [int(b.get(_q("id"))) for b in self.document.element.body.iter(_q("bookmarkStart"))
               if (b.get(_q("id")) or "").lstrip("-").isdigit()]
        self._bookmark_id = max(ids, default=0) + 1
        return self.document

    def _set_language(self):
        """The document language on the defaults of an empty base (spelling, hyphenation)."""
        from docx.oxml import OxmlElement

        rpr = self.document.styles.element.find(f"{_q('docDefaults')}/{_q('rPrDefault')}/{_q('rPr')}")
        if rpr is None:
            return
        lang = rpr.find(_q("lang"))
        if lang is None:
            lang = OxmlElement("w:lang")
            rpr.append(lang)
        lang.set(_q("val"), {"it": "it-IT", "en": "en-US"}[self.project.language])

    def _after_title_page(self):
        """A next-page section break after the model's content: the title page is section 0
        (first page without header or footer), the text is a new section."""
        from docx.enum.section import WD_SECTION

        body = self.document.element.body
        sentinel = body.get_or_add_sectPr()
        elements = [c for c in body if c is not sentinel]
        carrier = elements[-1] if elements and elements[-1].tag == _q("p") else None
        if carrier is not None and carrier.find(f"{_q('pPr')}/{_q('sectPr')}") is not None:
            carrier = None
        if carrier is None:
            carrier = body.add_p()
            elements.append(carrier)
        _drop_trailing_page_break(carrier)
        carrier.set_sectPr(sentinel.clone())
        for ref in sentinel.findall(_q("headerReference")) + sentinel.findall(_q("footerReference")):
            sentinel.remove(ref)
        for tag in ("pgNumType", "titlePg", "type"):
            for child in sentinel.findall(_q(tag)):
                sentinel.remove(child)
        sections = self.document.sections
        sections[0].different_first_page_header_footer = True
        sections[-1].start_type = WD_SECTION.NEW_PAGE
        sections[-1].header.is_linked_to_previous = False  # an empty header for the text
        self.title_count = len(elements)

    # paragraphs ----------------------------------------------------------------------------

    def _paragraph(self, style_key=None):
        p = self.document.add_paragraph()
        if style_key:
            p._p.get_or_add_pPr().style = self.styles[style_key]
        if self._after_table:
            p.paragraph_format.space_before = _pt(6)
            self._after_table = False
        self._at_page_start = False
        return p

    def _runs(self, paragraph, text: str):
        from docx.enum.text import WD_COLOR_INDEX

        for t in _tokens(text):
            value = self.token_text(t)
            if not value:
                continue
            run = paragraph.add_run(value)
            if t.bold:
                run.bold = True
            if t.italic:
                run.italic = True
            if t.kind == "code":
                run._r.get_or_add_rPr().style = self.styles["code"]
            elif t.kind == "todo":
                run.font.highlight_color = WD_COLOR_INDEX.YELLOW

    def _bookmark(self, p, name: str):
        from docx.oxml import OxmlElement

        start = OxmlElement("w:bookmarkStart")
        start.set(_q("id"), str(self._bookmark_id))
        start.set(_q("name"), name)
        end = OxmlElement("w:bookmarkEnd")
        end.set(_q("id"), str(self._bookmark_id))
        self._bookmark_id += 1
        return start, end

    def heading(self, level: int, text: str, entry: _TocEntry | None):
        new_page = level == 1 and not self._at_page_start
        self._after_table = False  # the heading's own space before separates it
        p = self._paragraph(f"heading{level}")
        if new_page:
            p.paragraph_format.page_break_before = True
        if entry is None:
            self._runs(p, text)
            return
        start, end = self._bookmark(p, entry.bookmark)
        p._p.append(start)
        self._runs(p, text)
        p._p.append(end)

    def paragraph(self, text: str):
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        p = self._paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        self._runs(p, text)

    def list_block(self, block: ListBlock):
        num_id = self._list_numbering(block.ordered)
        for item in block.items:
            p = self._paragraph()
            ppr = p._p.get_or_add_pPr()
            numpr = ppr.get_or_add_numPr()
            numpr.get_or_add_ilvl().val = 0
            numpr.get_or_add_numId().val = num_id
            ind = ppr.get_or_add_ind()
            ind.set(_q("left"), "720")
            ind.set(_q("hanging"), "360")
            self._runs(p, item)

    def _list_numbering(self, ordered: bool) -> int:
        """A new w:num (numbering restarting at 1) for one list; abstract definitions once."""
        from docx.opc.constants import CONTENT_TYPE as CT
        from docx.opc.constants import RELATIONSHIP_TYPE as RT
        from docx.oxml import parse_xml
        from docx.parts.numbering import NumberingPart

        if self._numbering is None:
            part = self.document.part
            try:
                numbering_part = part.part_related_by(RT.NUMBERING)
            except KeyError:
                blob = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                        f'<w:numbering {_nsdecl()}/>').encode("utf-8")
                numbering_part = NumberingPart.load(
                    part.package.next_partname("/word/numbering%d.xml"), CT.WML_NUMBERING, blob,
                    part.package)
                part.relate_to(numbering_part, RT.NUMBERING)
            root = numbering_part.element

            def next_id(tag, attr):
                values = [int(e.get(_q(attr))) for e in root.findall(_q(tag))
                          if (e.get(_q(attr)) or "").isdigit()]
                return max(values, default=0) + 1

            abstract = {}
            first_num = root.find(_q("num"))
            for kind, fmt, text in (("bullet", "bullet", "•"), ("ordered", "decimal", "%1.")):
                aid = next_id("abstractNum", "abstractNumId")
                element = parse_xml(
                    f'<w:abstractNum {_nsdecl()} w:abstractNumId="{aid}"><w:multiLevelType '
                    f'w:val="singleLevel"/><w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt '
                    f'w:val="{fmt}"/><w:lvlText w:val="{text}"/><w:lvlJc w:val="left"/><w:pPr>'
                    '<w:ind w:left="720" w:hanging="360"/></w:pPr></w:lvl></w:abstractNum>')
                if first_num is not None:
                    first_num.addprevious(element)
                else:
                    root.append(element)
                abstract[kind] = aid
            self._numbering = (root, abstract, next_id)
        root, abstract, next_id = self._numbering
        nid = next_id("num", "numId")
        element = parse_xml(
            f'<w:num {_nsdecl()} w:numId="{nid}"><w:abstractNumId w:val='
            f'"{abstract["ordered" if ordered else "bullet"]}"/><w:lvlOverride w:ilvl="0">'
            '<w:startOverride w:val="1"/></w:lvlOverride></w:num>')
        cleanup = root.find(_q("numIdMacAtCleanup"))
        if cleanup is not None:
            cleanup.addprevious(element)
        else:
            root.append(element)
        return nid

    def _field(self, paragraph, instruction: str, result: str):
        from docx.oxml import OxmlElement

        def run_with(child):
            r = OxmlElement("w:r")
            r.append(child)
            paragraph._p.append(r)
            return r

        begin = OxmlElement("w:fldChar")
        begin.set(_q("fldCharType"), "begin")
        run_with(begin)
        instr = OxmlElement("w:instrText")
        instr.set(f"{{{XML_NS}}}space", "preserve")
        instr.text = instruction
        run_with(instr)
        separate = OxmlElement("w:fldChar")
        separate.set(_q("fldCharType"), "separate")
        run_with(separate)
        paragraph.add_run(result)
        end = OxmlElement("w:fldChar")
        end.set(_q("fldCharType"), "end")
        run_with(end)

    def _caption(self, kind: str, number: int, caption: str):
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        p = self._paragraph("caption")
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        word = self.words[kind]
        p.add_run(f"{word} ")
        self._field(p, f" SEQ {word} \\* ARABIC ", str(number))
        if caption.strip():
            p.add_run(": ")
            self._runs(p, caption)
        return p

    def figure(self, block: Figure, chapter: _Chapter, number: int):
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.image.image import Image
        from docx.shared import Cm, Emu

        path = _resolve(chapter.path.parent, block.path)
        image = Image.from_file(str(path))
        text_width = Cm(self.text_width_cm)
        if block.width_cm is not None:
            width = Cm(block.width_cm)
        elif block.width_percent is not None:
            width = Emu(int(text_width * block.width_percent / 100))
        else:
            width = min(image.width, text_width)
        if width > text_width:
            self.warnings.append(f"{self.words['figure']} {number} ({chapter.name}:{block.line}): "
                                 f"width reduced to the text width ({self.text_width_cm:.1f} cm)")
            width = text_width
        height = Emu(int(image.height * width / image.width))
        max_height = Cm(self.text_height_cm * MAX_FIGURE_HEIGHT_SHARE)
        if height > max_height:
            width, height = Emu(int(width * max_height / height)), max_height
        p = self._paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.keep_with_next = True
        p.paragraph_format.space_before = _pt(6)
        p.add_run().add_picture(str(path), width=width, height=height)
        self._caption("figure", number, block.caption)

    def table(self, block: Table, number: int | None):
        from docx.enum.table import WD_TABLE_ALIGNMENT
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml import OxmlElement
        from docx.shared import Cm

        if number is not None:
            caption = self._caption("table", number, block.caption or "")
            caption.paragraph_format.keep_with_next = True
            caption.paragraph_format.space_before = _pt(6)
        columns = len(block.header)
        table = self.document.add_table(rows=1 + len(block.rows), cols=columns)
        table._tbl.tblPr.style = self.styles["table"]
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        width = Cm(self.text_width_cm / columns)
        align = {"left": WD_ALIGN_PARAGRAPH.LEFT, "center": WD_ALIGN_PARAGRAPH.CENTER,
                 "right": WD_ALIGN_PARAGRAPH.RIGHT}
        for column in table.columns:
            column.width = width
        last = len(block.rows)
        for r, values in enumerate([block.header] + block.rows):
            row = table.rows[r]
            # rows kept whole and together (keep with next but the last row), header repeated
            tr_pr = row._tr.get_or_add_trPr()
            tr_pr.append(OxmlElement("w:cantSplit"))
            if r == 0:
                tr_pr.append(OxmlElement("w:tblHeader"))
            for c, value in enumerate(values):
                cell = row.cells[c]
                cell.width = width
                p = cell.paragraphs[0]
                p.alignment = align[block.align[c] if c < len(block.align) else "left"]
                if r < last:
                    p.paragraph_format.keep_with_next = True
                before = len(p.runs)
                self._runs(p, value)
                if r == 0:
                    for run in p.runs[before:]:
                        run.bold = True
        self._after_table = True
        self._at_page_start = False

    def bibliography(self, entry: _TocEntry | None):
        from docx.shared import Cm

        self.heading(1, _escape(self.project.bibliography_title), entry)
        entries = self.project.entries
        for key, number in sorted(self.citation_numbers.items(), key=lambda kv: kv[1]):
            p = self._paragraph()
            p.paragraph_format.left_indent = Cm(0.75)
            p.paragraph_format.first_line_indent = Cm(-0.75)
            p.add_run(_entry_text(number, entries[key]))

    def toc(self):
        from docx.enum.text import WD_TAB_ALIGNMENT, WD_TAB_LEADER
        from docx.oxml import OxmlElement
        from docx.shared import Cm

        heading = self._paragraph("toc_heading")
        heading.add_run(self.project.toc_title)
        entries = self.toc_entries or [None]
        for i, entry in enumerate(entries):
            p = self._paragraph(f"toc{entry.level}" if entry else "toc1")
            p.paragraph_format.tab_stops.add_tab_stop(Cm(self.text_width_cm), WD_TAB_ALIGNMENT.RIGHT,
                                                       WD_TAB_LEADER.DOTS)
            if i == 0:
                self._field_begin(p, ' TOC \\o "1-3" \\h \\z \\u ')
            if entry is not None:
                link = OxmlElement("w:hyperlink")
                link.set(_q("anchor"), entry.bookmark)
                link.set(_q("history"), "1")
                p._p.append(link)
                for run in (p.add_run(entry.text), p.add_run("\t"), p.add_run(TOC_PLACEHOLDER)):
                    link.append(run._r)
            if i == len(entries) - 1:
                end = OxmlElement("w:fldChar")
                end.set(_q("fldCharType"), "end")
                r = OxmlElement("w:r")
                r.append(end)
                p._p.append(r)

    def _field_begin(self, paragraph, instruction: str):
        from docx.oxml import OxmlElement

        for kind, text in (("begin", None), (None, instruction), ("separate", None)):
            r = OxmlElement("w:r")
            if kind:
                child = OxmlElement("w:fldChar")
                child.set(_q("fldCharType"), kind)
            else:
                child = OxmlElement("w:instrText")
                child.set(f"{{{XML_NS}}}space", "preserve")
                child.text = text
            r.append(child)
            paragraph._p.append(r)

    # whole document ------------------------------------------------------------------------

    def build(self):
        project = self.project
        self.base()
        headings = [(chapter, block) for chapter in project.chapters for block in chapter.blocks
                    if isinstance(block, Heading)]
        has_bibliography = bool(self.citation_numbers)
        entries = {}
        if project.toc:
            for k, (_, block) in enumerate(headings, start=1):
                entries[id(block)] = _TocEntry(block.level, self.plain(block.text),
                                               f"_TocHmw{k:04d}")
            self.toc_entries = list(entries.values())
            if has_bibliography:
                self.toc_entries.append(_TocEntry(1, project.bibliography_title,
                                                  f"_TocHmw{len(headings) + 1:04d}"))
            self.toc()
        figure = table = 0
        for chapter in project.chapters:
            for block in chapter.blocks:
                if isinstance(block, Heading):
                    self.heading(block.level, block.text, entries.get(id(block)))
                elif isinstance(block, Paragraph):
                    self.paragraph(block.text)
                elif isinstance(block, ListBlock):
                    self.list_block(block)
                elif isinstance(block, Figure):
                    figure += 1
                    self.figure(block, chapter, figure)
                elif isinstance(block, Table):
                    if block.caption is not None:
                        table += 1
                    self.table(block, table if block.caption is not None else None)
        if has_bibliography:
            self.bibliography(self.toc_entries[-1] if project.toc else None)
        elif project.bibliography is not None:
            self.warnings.append(f"no citation in the text: the bibliography "
                                 f"({project.bibliography.name}) is left out")
        return self.document


def _pt(value):
    from docx.shared import Pt

    return Pt(value)


def _escape(text: str) -> str:
    """Text with the inline syntax characters escaped (shown literally by _tokens)."""
    return re.sub(r"([\\`*\[\]@])", r"\\\1", text)


def _authors(names: list[str]) -> str:
    names = ["et al." if n.strip().lower() == "others" else n for n in names]
    separator = "; " if any("," in n for n in names) else ", "
    return separator.join(names)


def _sentence(text: str) -> str:
    text = text.strip()
    return text if text.endswith((".", "?", "!")) else text + "."


def _entry_text(number: int, entry) -> str:
    """`[n] Authors. Title. Venue, Year. DOI: x.`, the missing parts left out."""
    from .headings import clean_title

    parts = []
    if entry.authors:
        parts.append(_authors([clean_title(a) for a in entry.authors]))
    if entry.title:
        parts.append(clean_title(entry.title))
    tail = ", ".join(x for x in (clean_title(entry.venue) if entry.venue else None, entry.year) if x)
    if tail:
        parts.append(tail)
    if entry.doi:
        parts.append(f"DOI: {entry.doi}")
    return f"[{number}] " + " ".join(_sentence(p) for p in parts if p.strip())


# --- after the layout: the title page as in the model --------------------------------------

_SPACING_DEFAULTS = ("before", "after", "beforeAutospacing", "afterAutospacing", "beforeLines",
                     "afterLines")


def _note_parts(document):
    for part in document.part.package.iter_parts():
        if str(part.partname) in ("/word/footnotes.xml", "/word/endnotes.xml"):
            yield part


def _freeze_title_styles(document, before, paragraphs) -> None:
    """Give the title page paragraphs frozen copies of their styles as they were in the
    model (before apply_layout changed Normal, the other paragraph styles and the defaults)."""
    styles_now = document.styles.element
    styles_before = before.styles.element
    old = {s.get(_q("styleId")): s for s in _style_elements(styles_before)
           if s.get(_q("type")) == "paragraph"}
    default = next((sid for sid, s in old.items()
                    if s.get(_q("default")) in ("1", "true", "on")), None)

    def style_of(p):
        ps = p.find(f"{_q('pPr')}/{_q('pStyle')}")
        sid = ps.get(_q("val")) if ps is not None else None
        return sid if sid in old else default

    closure, todo = set(), {style_of(p) for p in paragraphs} - {None}
    while todo:
        sid = todo.pop()
        if sid in closure or sid not in old:
            continue
        closure.add(sid)
        based = old[sid].find(_q("basedOn"))
        if based is not None:
            todo.add(based.get(_q("val")))
    taken_ids = {s.get(_q("styleId")) for s in _style_elements(styles_now)}
    taken_names = {_style_name(s).lower() for s in _style_elements(styles_now)}
    mapping = {}
    for sid in sorted(closure):
        new_id, n = "HMWFrontespizio" + re.sub(r"[^A-Za-z0-9]", "", sid), 2
        while new_id in taken_ids:
            new_id, n = f"HMWFrontespizio{re.sub(r'[^A-Za-z0-9]', '', sid)}{n}", n + 1
        taken_ids.add(new_id)
        mapping[sid] = new_id
    defaults_before = styles_before.find(f"{_q('docDefaults')}/{_q('pPrDefault')}/{_q('pPr')}/"
                                         f"{_q('spacing')}")
    for sid in sorted(closure):
        element = copy.deepcopy(old[sid])
        element.set(_q("styleId"), mapping[sid])
        element.attrib.pop(_q("default"), None)
        for tag in ("next", "link"):
            for child in element.findall(_q(tag)):
                element.remove(child)
        name = element.find(_q("name"))
        base_name = f"{_style_name(old[sid]) or sid} (frontespizio)"
        new_name, n = base_name, 2
        while new_name.lower() in taken_names:
            new_name, n = f"{base_name} {n}", n + 1
        taken_names.add(new_name.lower())
        if name is None:
            from docx.oxml import OxmlElement

            name = OxmlElement("w:name")
            element.insert(0, name)
        name.set(_q("val"), new_name)
        based = element.find(_q("basedOn"))
        if based is not None and based.get(_q("val")) in mapping:
            based.set(_q("val"), mapping[based.get(_q("val"))])
        else:
            if based is not None:
                element.remove(based)
            if defaults_before is not None:  # a root style: the model's paragraph defaults
                spacing = element.get_or_add_pPr().get_or_add_spacing()
                for attr in _SPACING_DEFAULTS:
                    value = defaults_before.get(_q(attr))
                    if value is not None and spacing.get(_q(attr)) is None:
                        spacing.set(_q(attr), value)
        styles_now.append(element)
    for p in paragraphs:
        sid = style_of(p)
        if sid not in mapping:
            continue
        ppr = p.find(_q("pPr"))
        if ppr is None:
            ppr = etree.SubElement(p, _q("pPr"))
            p.remove(ppr)
            p.insert(0, ppr)
        ps = ppr.find(_q("pStyle"))
        if ps is None:
            ps = etree.SubElement(ppr, _q("pStyle"))
            ppr.remove(ps)
            ppr.insert(0, ps)
        ps.set(_q("val"), mapping[sid])


TITLE_NOT_RESTORED = ("title page not restored to the model's formatting: the layout did not "
                      "keep its elements one for one, so it keeps the layout's formatting; "
                      "check it in Word")


def _element_text(element) -> str:
    return "".join(t.text or "" for t in element.iter(_q("t")))


def _restore_title_page(document, before, count: int) -> str | None:
    """Put the first count body elements (the title page) back as they were before
    apply_layout, with the page geometry of the model and its frozen styles; the section
    properties keep what apply_layout added (the footer with the page number).

    Only when apply_layout kept those elements one for one (same tags and texts): else
    nothing is replaced and the warning TITLE_NOT_RESTORED is returned."""
    body, old_body = document.element.body, before.element.body
    now = list(body)[:count]
    original = list(old_body)[:count]
    if len(now) != count or len(original) != count or any(
            a.tag != b.tag or _element_text(a) != _element_text(b) for a, b in zip(now, original)):
        return TITLE_NOT_RESTORED
    laid_sect = now[-1].find(f"{_q('pPr')}/{_q('sectPr')}")
    old_sect = original[-1].find(f"{_q('pPr')}/{_q('sectPr')}")
    restored = [copy.deepcopy(e) for e in original]
    for new, old in zip(now, restored):
        body.replace(new, old)
    if laid_sect is not None and old_sect is not None:
        for tag in ("pgSz", "pgMar"):
            geometry, laid = old_sect.find(_q(tag)), laid_sect.find(_q(tag))
            if geometry is not None and laid is not None:
                laid_sect.replace(laid, copy.deepcopy(geometry))
        ppr = restored[-1].find(_q("pPr"))
        ppr.replace(ppr.find(_q("sectPr")), laid_sect)
    paragraphs = [p for e in restored for p in e.iter(_q("p"))]
    notes = []
    for part in _note_parts(document):
        root = part.element if hasattr(part, "element") else etree.fromstring(part.blob)
        notes.append((part, root))
        paragraphs += list(root.iter(_q("p")))
    _freeze_title_styles(document, before, paragraphs)
    for part, root in notes:
        if not hasattr(part, "element"):
            part._blob = etree.tostring(root, xml_declaration=True, encoding="UTF-8",
                                        standalone=True)
    return None


# --- table of contents numbers -------------------------------------------------------------

def _page_offset(pages) -> int:
    """Physical page minus printed page number, from the numbers in the footers (the most
    common difference); 0 when none is readable."""
    offsets = Counter()
    for page in pages:
        lines = page.text.splitlines()
        last = lines[-1].strip() if lines else ""
        if page.has_page_number and re.fullmatch(r"[0-9]+", last):
            offsets[page.number - int(last)] += 1
    return offsets.most_common(1)[0][0] if offsets else 0


def _toc_numbers(pdf, toc_title: str, entries: list[_TocEntry]) -> tuple[dict, list[str]]:
    """bookmark -> printed page number of each entry located in the PDF, and warnings."""
    from .measure import measure_pdf, section_spans

    pages = measure_pdf(pdf)
    headings = [{"text": toc_title, "heading_level": 1}] + [
        {"text": e.text, "heading_level": e.level} for e in entries]
    spans = section_spans(pages, headings)
    offset = _page_offset(pages)
    located, j = [], 0
    for h in headings:
        title = " ".join(h["text"].split())
        if j < len(spans) and spans[j].title == title:
            located.append(spans[j].start_page)
            j += 1
        else:
            located.append(None)
    numbers, warnings = {}, []
    for entry, page in zip(entries, located[1:]):
        if page is None:
            warnings.append(f"page of '{entry.text}' not found in the rendered document: its "
                            f"table of contents entry shows {TOC_PLACEHOLDER} (update the table "
                            "in Word with F9)")
        else:
            numbers[entry.bookmark] = page - offset
    return numbers, warnings


def _fill_toc_numbers(document, numbers: dict) -> None:
    for link in document.element.body.iter(_q("hyperlink")):
        number = numbers.get(link.get(_q("anchor")))
        if number is None:
            continue
        texts = [t for t in link.iter(_q("t"))]
        if texts and texts[-1].text == TOC_PLACEHOLDER:
            texts[-1].text = str(number)


# --- entry point ---------------------------------------------------------------------------

def assemble(manifest: Path, out: Path) -> dict:
    """Write the .docx of a manifest to out (see the module docstring).

    Returns {"chapters", "figures", "tables", "citations", "warnings"}. Raises AssembleError
    when validate_manifest finds problems (nothing is written then).
    """
    import docx

    project, problems = _load(Path(manifest))
    if problems:
        raise AssembleError(problems)
    out = Path(out)
    builder = _Builder(project)
    work = Path(tempfile.mkdtemp(prefix="hmw-assemble-"))
    try:
        base = work / "base.docx"
        builder.build().save(str(base))
        laid = work / "impaginato.docx"
        apply_layout(base, project.layout, laid)
        document = docx.Document(str(laid))
        if builder.title_count:
            warning = _restore_title_page(document, docx.Document(str(base)), builder.title_count)
            if warning:
                builder.warnings.append(warning)
        final = work / "documento.docx"
        document.save(str(final))
        if builder.toc_entries:
            try:
                pdf = render_pdf(final, work / "pdf")
                numbers, warnings = _toc_numbers(pdf, project.toc_title, builder.toc_entries)
                builder.warnings += warnings
                _fill_toc_numbers(document, numbers)
                document.save(str(final))
            except RenderError as exc:
                builder.warnings.append(NO_TOC_NUMBERS if exc.missing_tool
                                        else f"{NO_TOC_NUMBERS} ({exc})")
            except ImportError as exc:  # pdfplumber, needed to read the rendered pages
                builder.warnings.append(f"{NO_TOC_NUMBERS} (missing Python package: "
                                        f"{exc.name or exc})")
            except Exception as exc:  # an unreadable PDF: the document itself is complete
                builder.warnings.append(f"{NO_TOC_NUMBERS} (the rendered PDF could not be "
                                        f"read: {type(exc).__name__}: {exc})")
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(final, out)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return {"chapters": len(project.chapters), "figures": builder.figures,
            "tables": builder.tables, "citations": len(builder.citation_numbers),
            "warnings": builder.warnings}


def add_arguments(parser):
    parser.add_argument("manifest", help="manifest.yaml: layout, chapters, title page, "
                                         "bibliography (paths relative to its folder)")
    parser.add_argument("-o", "--output", required=True, help="new .docx to write")


def run(args) -> int:
    from . import cli

    if Path(args.output).suffix.lower() != ".docx":
        print(f"error: the output must be a .docx file: {args.output}", file=sys.stderr)
        return 2
    if cli.refuses_existing_output(args.output, sources=[args.manifest]):
        return 2
    problems = validate_manifest(Path(args.manifest))
    if problems:
        for problem in problems:
            print(f"error: {problem}", file=sys.stderr)
        return 2
    try:
        result = assemble(Path(args.manifest), Path(args.output))
    except AssembleError as exc:
        for problem in exc.problems:
            print(f"error: {problem}", file=sys.stderr)
        return 2
    except (OSError, LayoutError, ValueError) as exc:
        print(f"error: cannot assemble {args.manifest}: {exc}", file=sys.stderr)
        return 2
    result = {"output": str(args.output), **result}
    lines = [f"wrote {args.output}: {result['chapters']} chapter(s), {result['figures']} "
             f"figure(s), {result['tables']} table(s), {result['citations']} cited source(s)"]
    lines += [f"warning: {w}" for w in result["warnings"]]

    class _View:  # -o is the document here, never a JSON path
        json = getattr(args, "json", False)
        output = None

    cli.emit(result, _View, text="\n".join(lines))
    return 0
