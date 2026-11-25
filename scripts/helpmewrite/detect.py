"""Find drafts and guidelines candidates in a work folder."""
import os
import re
from pathlib import Path

SKIP_DIRS = {".git", ".help-me-write", "__pycache__", "node_modules", ".venv", "venv",
             ".ipynb_checkpoints"}
SKIP_SUFFIXES = ("-revisionato", "-help-me-write")
GUIDELINE_WORDS = ("linee guida", "linee-guida", "linee_guida", "lineeguida", "regolamento",
                   "norme", "facsimile", "modello", "template", "bando", "guidelines")
DRAFT_WORDS = ("relazione", "report", "bozza", "draft", "tesi", "capitolo")
COPY_SUFFIXES = ("-revisionato", "-formattato", "-differenze")
GUIDELINE_EXT = {".docx", ".pdf", ".md", ".txt", ".tex"}
EMPTY_LIMIT = 200
_COMMENT = re.compile(r"(?<!\\)%.*")
_HEADING = re.compile(r"\\(?:chapter|section)\*?(?:\[[^\]]*\])?\{(?:[^{}]|\{[^{}]*\})*\}")


def _skip_dir(name: str) -> bool:
    return name in SKIP_DIRS or name.lower().endswith(SKIP_SUFFIXES)


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


def detect(work) -> dict:
    from . import headings

    work = Path(work)
    drafts, guidelines, ignored = [], [], []
    for root, dirs, files in os.walk(work):
        dirs[:] = sorted(d for d in dirs if not _skip_dir(d))
        for name in sorted(files):
            path = Path(root) / name
            rel = path.relative_to(work).as_posix()
            suffix = path.suffix.lower()
            if name.startswith("~$"):
                ignored.append(rel)
            elif suffix in GUIDELINE_EXT and _is_guideline(name):
                guidelines.append(rel)
            elif suffix == ".docx":
                if path.stem.lower().endswith(COPY_SUFFIXES):
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
            parts = headings.tex_parts(path)
            item["parts"] = [p.relative_to(work).as_posix() if p.is_absolute()
                             else Path(os.path.relpath(p, work)).as_posix() for p in parts]
            item["empty_parts"] = [r for r, p in zip(item["parts"], parts) if _is_empty_part(p)]
            item["words"] = sum(_words(_tex_text(p)) for p in [path, *parts])
        elif fmt == "word":
            from . import extract
            item["words"] = sum(_words(p["text"])
                                for p in extract.extract(path)["paragraphs"])
        else:
            item["words"] = _words(_read(path))
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
