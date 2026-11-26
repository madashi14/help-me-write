"""Find drafts and guidelines candidates in a work folder."""
import os
import re
from pathlib import Path

SKIP_DIRS = {".git", ".help-me-write", "__pycache__", "node_modules", ".venv", "venv",
             ".ipynb_checkpoints"}
# help-me-write's own outputs: working copies (`<name>-help-me-write`, `<name>-v2-help-me-write`)
# and corrected copies (`<name>-revisionato`, `<name>-help-me-write-revisionato-2`)
OUTPUT_MARKS = ("-help-me-write", "-revisionato")
GUIDELINE_WORDS = ("linee guida", "linee-guida", "linee_guida", "lineeguida", "regolamento",
                   "norme", "facsimile", "modello", "template", "bando", "guidelines")
DRAFT_WORDS = ("relazione", "report", "bozza", "draft", "tesi", "capitolo")
COPY_SUFFIXES = ("-revisionato", "-formattato", "-differenze")
GUIDELINE_EXT = {".docx", ".pdf", ".md", ".txt", ".tex"}
EMPTY_LIMIT = 200
_COMMENT = re.compile(r"(?<!\\)%.*")
_HEADING = re.compile(r"\\(?:chapter|section)\*?(?:\[[^\]]*\])?\{(?:[^{}]|\{[^{}]*\})*\}")


def is_output_name(name: str) -> bool:
    """True for a file or folder name of help-me-write's outputs (`*-help-me-write*`,
    `*-revisionato*`)."""
    low = name.lower()
    return any(mark in low for mark in OUTPUT_MARKS)


def skip_dir(name: str) -> bool:
    """The shared skip rule: True for a folder that no scan enters and no copy takes.

    Used by detect, material, the copies of `format` and `track` (.tex) and the source
    search of `bib`: tool and cache folders, the state folder `.help-me-write` and every
    help-me-write output folder (`*-help-me-write*`, `*-revisionato*`)."""
    return name in SKIP_DIRS or is_output_name(name)


def is_output_pdf(name: str) -> bool:
    """True for a PDF help-me-write writes: in an output's name, or a PDF of differences
    (`*-differenze.pdf`, `*-differenze-<N>.pdf`), or a copy (`-revisionato`, `-formattato`)."""
    stem = Path(name).stem.lower()
    return is_output_name(stem) or bool(re.search(r"-(?:differenze|formattato)(?:-\d+)?$", stem))


def _is_guideline(name: str) -> bool:
    low = name.lower()
    return any(w in low for w in GUIDELINE_WORDS)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _words(text: str) -> int:
    return len(text.split())


def _tex_text(path: Path) -> str:
    return _COMMENT.sub("", _read(path))


def _is_empty_part(path: Path) -> bool:
    text = _HEADING.sub("", _tex_text(path))
    return len(re.sub(r"\s+", "", text)) < EMPTY_LIMIT


def _safe(fn, arg, default):
    """fn(arg), or default if the file cannot be read or parsed."""
    try:
        return fn(arg)
    except Exception:
        return default


def detect(work) -> dict:
    from . import headings

    work = Path(work)
    drafts, guidelines, ignored = [], [], []
    for root, dirs, files in os.walk(work):
        dirs[:] = sorted(d for d in dirs if not skip_dir(d))
        for name in sorted(files):
            path = Path(root) / name
            rel = path.relative_to(work).as_posix()
            suffix = path.suffix.lower()
            if name.startswith("~$"):
                ignored.append(rel)
            elif suffix in GUIDELINE_EXT and _is_guideline(name):
                guidelines.append(rel)
            elif suffix == ".docx":
                if path.stem.lower().endswith(COPY_SUFFIXES) or is_output_name(path.stem):
                    ignored.append(rel)
                else:
                    drafts.append((rel, "word", path))
            elif suffix == ".tex":
                if re.search(r"^\s*\\documentclass", _tex_text(path), re.MULTILINE):
                    drafts.append((rel, "latex", path))
            elif suffix in (".md", ".txt"):
                if any(w in name.lower() for w in DRAFT_WORDS):
                    drafts.append((rel, "markdown" if suffix == ".md" else "text", path))
            elif suffix == ".pdf":
                if is_output_pdf(name):  # a PDF of differences or of a copy is no draft
                    ignored.append(rel)
                else:
                    drafts.append((rel, "pdf", path))
    stems = {Path(rel).stem.lower() for rel, fmt, _ in drafts if fmt != "pdf"}
    result = []
    for rel, fmt, path in drafts:
        item = {"path": rel, "format": fmt, "parts": [], "empty_parts": [], "words": None}
        if fmt == "pdf":
            if path.stem.lower() in stems:
                ignored.append(rel)
                continue
        elif fmt == "latex":
            try:
                parts = headings.tex_parts(path)
            except Exception:
                parts = []
            item["parts"] = [p.relative_to(work).as_posix() if p.is_absolute()
                             else Path(os.path.relpath(p, work)).as_posix() for p in parts]
            item["empty_parts"] = [r for r, p in zip(item["parts"], parts)
                                   if _safe(_is_empty_part, p, False)]
            counts = [_safe(lambda q: _words(_tex_text(q)), p, None) for p in [path, *parts]]
            item["words"] = sum(c for c in counts if c is not None)
        elif fmt == "word":
            from . import extract
            item["words"] = _safe(lambda q: sum(
                _words(p["text"]) for p in extract.extract(q)["paragraphs"]), path, None)
        else:
            item["words"] = _safe(lambda q: _words(_read(q)), path, None)
        result.append(item)
    state = work / ".help-me-write" / "progetto.md"
    return {"state": state.relative_to(work).as_posix() if state.is_file() else None,
            "drafts": sorted(result, key=lambda d: d["path"]),
            "guidelines": sorted(guidelines), "ignored": sorted(ignored)}


def add_arguments(parser):
    parser.add_argument("work", help="work folder to scan")


def run(args) -> int:
    from . import cli

    work = Path(args.work)
    if not work.is_dir():
        raise cli.CliError(f"not a folder: {work}")
    data = detect(work)
    lines = [f"state: {data['state'] or 'none'}"]
    lines += [f"draft ({d['format']}): {d['path']}, {d['words']} words"
              + (f", empty parts: {', '.join(d['empty_parts'])}" if d["empty_parts"] else "")
              for d in data["drafts"]]
    lines += [f"guidelines: {g}" for g in data["guidelines"]]
    cli.emit(data, args, text="\n".join(lines))
    return 0
