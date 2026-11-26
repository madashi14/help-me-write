"""Section headings of a document, from where they are most reliable.

.docx: the paragraphs with a heading style (extract.extract). .tex: \\chapter, \\section and
\\subsection of the main file and of the files it \\input or \\include, plus the headings
LaTeX generates (table of contents, lists of figures and tables, bibliography: \\bibliography,
\\printbibliography or a hand-written thebibliography). .pdf: its bookmarks
(outline). Every heading is a dict with "text" and "heading_level" (the keys section_spans
reads); those from .tex also have "file" (relative to the folder of the main file) and "line".
"""
import os
import re
import unicodedata
from pathlib import Path

_COMMAND = re.compile(r"\\(chapter|section|subsection|tableofcontents|listoffigures|listoftables"
                      r"|bibliography|printbibliography|input|include|begin|end)(?![a-zA-Z])")
_GENERATED = {  # command -> (Italian, English)
    "tableofcontents": ("Indice", "Contents"),
    "listoffigures": ("Elenco delle figure", "List of Figures"),
    "listoftables": ("Elenco delle tabelle", "List of Tables"),
}
_BIBLIOGRAPHY_COMMANDS = ("bibliography", "printbibliography", "thebibliography")
_BIBLIOGRAPHY = {  # (book-like class?) -> (Italian, English)
    True: ("Bibliografia", "Bibliography"),
    False: ("Riferimenti bibliografici", "References"),
}
_BOOK_CLASSES = {"report", "book", "scrreprt", "scrbook", "memoir"}
_LEVELS_WITH_CHAPTER = {"chapter": 1, "section": 2, "subsection": 3}
_LEVELS_WITHOUT_CHAPTER = {"section": 1, "subsection": 2}


# --- reading the sources -------------------------------------------------------------------

def _strip_comments(text: str) -> str:
    """Text without comments (an unescaped % to the end of the line); lines are kept."""
    out = []
    for line in text.split("\n"):
        i = 0
        while i < len(line):
            if line[i] == "\\":
                i += 2
                continue
            if line[i] == "%":
                line = line[:i]
                break
            i += 1
        out.append(line)
    return "\n".join(out)


def _skip_space(text: str, i: int) -> int:
    while i < len(text) and text[i].isspace():
        i += 1
    return i


def _balanced(text: str, i: int, open_: str, close: str) -> tuple[str, int] | None:
    """The content of the group opening at text[i] and the index after it, or None."""
    if i >= len(text) or text[i] != open_:
        return None
    depth, j = 0, i
    while j < len(text):
        c = text[j]
        if c == "\\":
            j += 2
            continue
        if c == open_:
            depth += 1
        elif c == close:
            depth -= 1
            if depth == 0:
                return text[i + 1:j], j + 1
        j += 1
    return None


def _argument(text: str, i: int) -> tuple[str, int] | None:
    """The {argument} after a command at text[i], skipping a * and a [short title]."""
    i = _skip_space(text, i)
    if i < len(text) and text[i] == "*":
        i = _skip_space(text, i + 1)
    optional = _balanced(text, i, "[", "]")
    if optional:
        i = _skip_space(text, optional[1])
    return _balanced(text, i, "{", "}")


def _read(path: Path) -> str | None:
    try:
        return _strip_comments(path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return None


def _resolve_include(base: Path, name: str) -> Path | None:
    name = name.strip()
    if not name:
        return None
    path = base / name
    if path.suffix.lower() != ".tex":
        path = path.with_name(path.name + ".tex")
    return path if path.is_file() else None


def _walk(main: Path):
    """Yield ("file", path), ("command", name, text_after, index, file, line) events in
    document order, following \\input and \\include; stops at \\end{document}."""
    base = main.parent
    visited = {main.resolve()}
    state = {"ended": False}

    def walk(path: Path):
        text = _read(path)
        if text is None:
            return
        for m in _COMMAND.finditer(text):
            if state["ended"]:
                return
            name, line = m.group(1), text.count("\n", 0, m.start()) + 1
            arg = _argument(text, m.end())
            if name == "end":
                if arg and arg[0].strip() == "document":
                    state["ended"] = True
                    return
                continue
            if name == "begin":  # only a hand-written bibliography makes a heading
                if arg and arg[0].strip() == "thebibliography":
                    yield ("command", "thebibliography", "", path, line)
                continue
            if name in ("input", "include"):
                target = _resolve_include(base, arg[0]) if arg else None
                if target is None or target.resolve() in visited:
                    continue
                visited.add(target.resolve())
                yield ("file", target)
                yield from walk(target)
                continue
            yield ("command", name, arg[0] if arg else "", path, line)

    yield from walk(main)


def tex_parts(main: Path) -> list[Path]:
    """The files \\input or \\include d (existing, in order, each once), without main."""
    return [event[1] for event in _walk(Path(main)) if event[0] == "file"]


# --- title text ----------------------------------------------------------------------------

_ACCENTS = {"`": "\u0300", "'": "\u0301", "^": "\u0302", "~": "\u0303", "=": "\u0304",
            ".": "\u0307", '"': "\u0308"}
_ACCENT_COMMAND = re.compile(r"\\([`'^~=.\"])\s*(?:\{\s*(\\?[a-zA-Z])\s*\}|(\\?[a-zA-Z]))")
_LETTER_ACCENT = re.compile(r"\\([cvu])(?:\s*\{\s*([a-zA-Z])\s*\}|\s+([a-zA-Z]))")
_LETTER_MARKS = {"c": "\u0327", "v": "\u030c", "u": "\u0306"}


def _remove_command(text: str, name: str) -> str:
    """Text without \\name{...} (and \\name*{...})."""
    pattern = re.compile(r"\\" + name + r"(?![a-zA-Z])")
    while (m := pattern.search(text)):
        arg = _argument(text, m.end())
        text = text[:m.start()] + (text[arg[1]:] if arg else text[m.end():])
    return text


def _accent(mark: str, letter: str) -> str:
    letter = {"\\i": "i", "\\j": "j"}.get(letter, letter)
    return unicodedata.normalize("NFC", letter + mark)


def clean_title(raw: str) -> str:
    """The plain text of a heading's argument (see the module docstring)."""
    text = _remove_command(_remove_command(raw, "label"), "footnote")
    text = _ACCENT_COMMAND.sub(lambda m: _accent(_ACCENTS[m.group(1)], m.group(2) or m.group(3)),
                               text)
    text = _LETTER_ACCENT.sub(lambda m: _accent(_LETTER_MARKS[m.group(1)], m.group(2) or m.group(3)),
                              text)
    for old, new in (("\\&", "&"), ("\\%", "%"), ("\\_", "_"), ("\\#", "#"), ("\\$", "$"),
                     ("\\\\", " "), ("---", "\u2014"), ("--", "\u2013"), ("~", " ")):
        text = text.replace(old, new)
    text = re.sub(r"\\[a-zA-Z]+\*?", " ", text)  # other commands: dropped (their arguments stay)
    text = re.sub(r"[{}]", "", text)
    return " ".join(text.split())


# --- tex headings --------------------------------------------------------------------------

def _language(text: str) -> str:
    """"it" or "en" from babel or polyglossia (English without either). In babel's options
    the main language is `main=<language>`, else the last one."""
    found = "en"
    for m in re.finditer(r"\\usepackage\s*\[([^\]]*)\]\s*\{[^}]*\b(?:babel|polyglossia)\b[^}]*\}"
                         r"|\\set(?:main|default)language\s*(?:\[[^\]]*\])?\s*\{(\w+)\}", text):
        options = (m.group(1) or m.group(2) or "").lower()
        main = re.search(r"\bmain\s*=\s*([a-z]+)", options)
        words = [main.group(1)] if main else re.findall(r"[a-z]+", options)
        for w in words:
            if w in ("italian", "italiano"):
                found = "it"
            elif w in ("english", "american", "british", "usenglish", "ukenglish"):
                found = "en"
    return found


def tex_headings(main: Path) -> list[dict]:
    """Headings of a LaTeX document: {"text", "heading_level", "file", "line"} each."""
    main = Path(main)
    base = main.resolve().parent
    source = _read(main) or ""
    cls = re.search(r"\\documentclass\s*(?:\[[^\]]*\])?\s*\{([^}]*)\}", source)
    book_like = bool(cls) and cls.group(1).strip() in _BOOK_CLASSES

    events, texts = [], [source]
    for event in _walk(main):
        if event[0] == "file":
            texts.append(_read(event[1]) or "")
        else:
            events.append(event)
    index = 0 if _language("\n".join(texts)) == "it" else 1
    has_chapter = any(e[1] == "chapter" for e in events)
    levels = _LEVELS_WITH_CHAPTER if has_chapter else _LEVELS_WITHOUT_CHAPTER

    headings = []
    for _, name, arg, path, line in events:
        if name in levels:
            text, level = clean_title(arg), levels[name]
        elif name in _GENERATED:
            text, level = _GENERATED[name][index], 1
        elif name in _BIBLIOGRAPHY_COMMANDS:
            text, level = _BIBLIOGRAPHY[book_like][index], 1
        else:
            continue
        if text:
            rel = os.path.relpath(path.resolve(), base).replace(os.sep, "/")
            headings.append({"text": text, "heading_level": level, "file": rel, "line": line})
    return headings


# --- PDF bookmarks -------------------------------------------------------------------------

def pdf_headings(pdf: Path) -> list[dict] | None:
    """The bookmarks of a PDF as headings, or None when it has none (or cannot be read)."""
    try:
        import pdfplumber

        with pdfplumber.open(str(pdf)) as doc:
            outlines = list(doc.doc.get_outlines())
    except Exception:
        return None
    headings = []
    for level, title, *_ in outlines:
        if isinstance(title, bytes):
            title = title.decode("utf-8", errors="replace")
        title = " ".join(str(title or "").split())
        if title:
            headings.append({"text": title, "heading_level": int(level)})
    return headings or None


def document_headings(doc: Path, pdf: Path) -> tuple[list[dict] | None, str]:
    """(headings, source) of a document and its rendered PDF; source is "docx", "tex",
    "pdf-bookmarks" or "none" (headings None)."""
    doc = Path(doc)
    suffix = doc.suffix.lower()
    if suffix == ".docx":
        from .extract import extract

        return [p for p in extract(doc)["paragraphs"] if p["heading_level"] is not None], "docx"
    if suffix == ".tex":
        found = tex_headings(doc)
        if found:
            return found, "tex"
    found = pdf_headings(pdf)
    return (found, "pdf-bookmarks") if found else (None, "none")
