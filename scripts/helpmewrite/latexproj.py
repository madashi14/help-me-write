"""A new LaTeX project whose layout satisfies the guidelines (mode 1, LaTeX branch).

`hmw latex-init <folder> --layout L --chapters capitoli.json` writes main.tex (preamble from
the layout), frontespizio.tex (from modelli/latex/), one file per chapter, an empty
immagini/ folder, .latexmkrc and, on request, bibliografia.bib. A title-page value that is
not given becomes `[DA VERIFICARE: <key>]`.
"""
import json
import re
import sys
from pathlib import Path

from .fonts import DOCX_FONT
from .layout import Layout, LayoutError, geometry_paper, load_layout, setstretch_factor

MODELLI = Path(__file__).resolve().parents[2] / "modelli" / "latex"

TITLE_PAGE_KEYS = {
    "unibo": ["anno_accademico", "studente", "matricola", "corso", "codice_corso",
              "struttura", "argomento", "referente"],
    "generico": ["titolo", "autore", "istituzione", "data"],
}
TEX_GYRE = {"times": "TeX Gyre Termes", "helvetica": "TeX Gyre Heros",
            "courier": "TeX Gyre Cursor"}
KINDS = {"introduzione", "corpo", "conclusione", "allegato"}
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_ESCAPES = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
            "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}",
            "^": r"\textasciicircum{}"}


class LatexProjectError(Exception):
    pass


def tex_escape(text: str) -> str:
    """Protect the characters special to TeX: & % $ # _ { } ~ ^ \\."""
    return "".join(_ESCAPES.get(c, c) for c in text)


def _macro(key: str) -> str:
    """Control-sequence name of a key: underscores are not letters, so camelCase."""
    first, *rest = key.split("_")
    return first + "".join(p.capitalize() for p in rest)


def _check_chapters(chapters) -> None:
    if not isinstance(chapters, list) or not chapters:
        raise LatexProjectError("the chapter list must be a non-empty JSON list")
    seen = set()
    for ch in chapters:
        if not isinstance(ch, dict) or not isinstance(ch.get("title"), str) \
                or not ch["title"].strip():
            raise LatexProjectError(f"chapter without a title: {ch!r}")
        cid = ch.get("id")
        if not isinstance(cid, str) or not _ID_RE.match(cid):
            raise LatexProjectError(f"invalid chapter id {cid!r} (use [a-z0-9][a-z0-9-]*)")
        if cid in seen:
            raise LatexProjectError(f"duplicate chapter id {cid!r}")
        seen.add(cid)
        if ch.get("kind") not in KINDS:
            raise LatexProjectError(f"chapter {cid!r}: kind must be one of {sorted(KINDS)}")


def _data_block(keys, values) -> str:
    lines = ["% --- DATI DEL FRONTESPIZIO ---"]
    for key in keys:
        value = values.get(key)
        if value is None or not str(value).strip():
            body = "[DA VERIFICARE: %s]" % key
            if "_" in key:  # a bare underscore is a TeX error in text
                body = r"\detokenize{%s}" % body
        else:
            body = tex_escape(" ".join(str(value).split()))
        lines.append(r"\newcommand{\%s}{%s}" % (_macro(key), body))
    lines.append("% --- FINE DATI ---")
    return "\n".join(lines)


def _main_tex(layout: Layout, chapters, language, bibliography, data_block) -> str:
    size = layout.font_size_pt
    if size not in (10, 11, 12):
        raise LatexProjectError(
            f"font size {size:g} pt is not available in the LaTeX classes (use 10, 11 or 12)")
    size = int(size)
    try:
        stretch = (setstretch_factor(layout.line_pitch_pt, size)
                   if layout.line_pitch_pt is not None else 1)
    except LayoutError as exc:
        raise LatexProjectError(str(exc)) from None
    font = DOCX_FONT.get(layout.family, layout.docx_font)
    fallback = TEX_GYRE.get(layout.family, "TeX Gyre Termes")
    babel = {"it": "italian", "en": "english"}[language]
    m = layout.margins_cm
    paper = geometry_paper(layout)
    includes = "\n".join(
        r"\include{capitoli/%02d-%s}" % (i, ch["id"]) for i, ch in enumerate(chapters, 1))
    bib = (r"\bibliographystyle{unsrt}" "\n" r"\bibliography{bibliografia}" "\n"
           if bibliography else "")
    return rf"""% !TeX program = xelatex
\documentclass[{size}pt,a4paper,oneside]{{report}}
\usepackage[{babel}]{{babel}}
\usepackage{{fontspec}}
\IfFontExistsTF{{{font}}}{{\setmainfont{{{font}}}}}{{\setmainfont{{{fallback}}}}}
\usepackage[{paper},top={m['top']}cm,bottom={m['bottom']}cm,left={m['left']}cm,right={m['right']}cm]{{geometry}}
\usepackage{{setspace}}
\setstretch{{{stretch}}}
\usepackage{{indentfirst}}
\setlength{{\parindent}}{{1cm}}
\setlength{{\parskip}}{{0pt}}
\emergencystretch=2em
\usepackage{{graphicx}}
\graphicspath{{{{immagini/}}}}
\usepackage{{caption}}
\usepackage{{booktabs}}
\usepackage{{titlesec}}
\titleformat{{\chapter}}[hang]{{\normalfont\Large\bfseries}}{{\thechapter.}}{{1em}}{{}}
\titlespacing*{{\chapter}}{{0pt}}{{0pt}}{{1.5\baselineskip}}
\usepackage{{fancyhdr}}
\pagestyle{{fancy}}
\fancyhf{{}}
\fancyfoot[C]{{\thepage}}
\renewcommand{{\headrulewidth}}{{0pt}}
\fancypagestyle{{plain}}{{%
    \fancyhf{{}}%
    \fancyfoot[C]{{\thepage}}%
    \renewcommand{{\headrulewidth}}{{0pt}}%
}}
\usepackage[unicode,hidelinks]{{hyperref}}

{data_block}

\begin{{document}}

\input{{frontespizio}}

\pagenumbering{{roman}}
\tableofcontents
\clearpage
\pagenumbering{{arabic}}

{includes}

{bib}\end{{document}}
"""


def new_latex_project(out_dir, layout: Layout, chapters: list, language: str = "it",
                      title_page: str = "unibo", values: dict | None = None,
                      bibliography: bool = False) -> list[Path]:
    """Write the project into out_dir (new or empty); return the files written."""
    out_dir = Path(out_dir)
    values = dict(values or {})
    if language not in ("it", "en"):
        raise LatexProjectError(f"unknown language {language!r} (use it or en)")
    if title_page not in TITLE_PAGE_KEYS:
        raise LatexProjectError(f"unknown title page {title_page!r} (use unibo or generico)")
    keys = TITLE_PAGE_KEYS[title_page]
    unknown = sorted(k for k in values if k not in keys)
    if unknown:
        raise LatexProjectError(
            f"unknown title page keys: {', '.join(unknown)} (valid: {', '.join(keys)})")
    _check_chapters(chapters)
    model = MODELLI / f"frontespizio-{title_page}.tex"
    try:
        front = model.read_text(encoding="utf-8")
    except OSError as exc:
        raise LatexProjectError(f"title page model not found: {model} ({exc.strerror})") from None
    main = _main_tex(layout, chapters, language, bibliography, _data_block(keys, values))
    if out_dir.exists() and (not out_dir.is_dir() or any(out_dir.iterdir())):
        raise LatexProjectError(f"output already exists and is not an empty folder: {out_dir}")

    files = {"main.tex": main, "frontespizio.tex": front, ".latexmkrc": "$pdf_mode = 5;\n"}
    for i, ch in enumerate(chapters, 1):
        files[f"capitoli/{i:02d}-{ch['id']}.tex"] = (
            f"\\chapter{{{tex_escape(ch['title'])}}}\\label{{cap:{ch['id']}}}\n\n"
            "% help-me-write: testo da scrivere\n")
    if bibliography:
        files["bibliografia.bib"] = ""
    try:
        (out_dir / "immagini").mkdir(parents=True, exist_ok=True)
        (out_dir / "capitoli").mkdir(exist_ok=True)
        written = []
        for name, text in files.items():
            path = out_dir / name
            path.write_text(text, encoding="utf-8", newline="\n")
            written.append(path)
    except OSError as exc:
        raise LatexProjectError(f"cannot write {out_dir}: {exc.strerror or exc}") from None
    return written


def add_arguments(parser):
    parser.add_argument("out_dir", help="new (or empty) folder for the project")
    parser.add_argument("--layout", required=True, help="layout JSON from `hmw layout`")
    parser.add_argument("--chapters", required=True, help="chapter list JSON (state outline)")
    parser.add_argument("--values", help="JSON of title page values")
    parser.add_argument("--title-page", choices=sorted(TITLE_PAGE_KEYS), default="unibo")
    parser.add_argument("--language", choices=["it", "en"], default="it")
    parser.add_argument("--bibliography", action="store_true",
                        help="add bibliografia.bib and the bibliography commands")


def _load_json(path, what):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise LatexProjectError(f"cannot read {what} file {path}: {exc}") from None


def run(args) -> int:
    from . import cli

    if cli.refuses_existing_output(args.out_dir, folder_ok_if_empty=True):
        return 2
    try:
        layout = load_layout(args.layout)
        chapters = _load_json(args.chapters, "chapters")
        values = _load_json(args.values, "values") if args.values else None
        if values is not None and not isinstance(values, dict):
            raise LatexProjectError("the values file must be a JSON object")
        files = new_latex_project(args.out_dir, layout, chapters, args.language,
                                  args.title_page, values, args.bibliography)
    except (LatexProjectError, LayoutError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    rel = [str(p.relative_to(args.out_dir)) for p in files]
    cli.emit({"output": str(args.out_dir), "files": rel}, args,
             text=f"wrote LaTeX project {args.out_dir} ({len(files)} files)")
    return 0
