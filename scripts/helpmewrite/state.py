"""The resumable project state file `.help-me-write/progetto.md` (YAML header + Markdown body)."""
import hashlib
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

import yaml

VERSION = 1
MODES = ("da-zero", "bozza-parziale", "solo-revisione")
FORMATS = ("latex", "word")
KINDS = ("introduzione", "corpo", "conclusione", "allegato")
STATUSES = ("da-fare", "intervista-fatta", "scritto", "approvato", "revisionato")
ID_RE = re.compile(r"[a-z0-9][a-z0-9-]*\Z")
SCALAR_KEYS = ("mode", "document_type", "profile", "format", "language", "draft", "output",
               "outline_approved", "title_page_approved")
PATH_KEYS = ("draft", "output")
HEADER_KEYS = ("version",) + SCALAR_KEYS + ("chapters", "fingerprints")
CHAPTER_KEYS = ("id", "title", "kind", "status", "source", "notes")
STATE_DIR = ".help-me-write"
STATE_FILE = "progetto.md"
DEFAULT_BODY = "## Decisioni\n\n## Domande aperte\n"
_HEADER = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.DOTALL)
_HEADER_EMPTY = re.compile(r"\A---[ \t]*\r?\n---[ \t]*(?:\r?\n|\Z)")


class StateError(Exception):
    def __init__(self, problems):
        self.problems = [problems] if isinstance(problems, str) else list(problems)
        super().__init__("; ".join(self.problems))


@dataclass
class Chapter:
    id: str
    title: str
    kind: str
    status: str = "da-fare"
    source: str | None = None
    notes: str | None = None


@dataclass
class ProjectState:
    mode: str
    document_type: str | None = None
    profile: str | None = None
    format: str | None = None
    language: str = "it"
    draft: str | None = None
    output: str | None = None
    outline_approved: bool = False
    title_page_approved: bool = False
    chapters: list = field(default_factory=list)
    fingerprints: dict = field(default_factory=dict)
    body: str = DEFAULT_BODY


def state_path(work) -> Path:
    return Path(work) / STATE_DIR / STATE_FILE


# --- parsing and validation ---------------------------------------------------------------

def _opt_str(value, where, problems):
    if value is not None and not isinstance(value, str):
        problems.append(f"{where}: expected text or null, got {value!r}")
        return None
    return value


def _chapter(raw, i, problems):
    where = f"chapters[{i}]"
    if not isinstance(raw, dict):
        problems.append(f"{where}: expected a mapping, got {raw!r}")
        return None
    for key in sorted(set(raw) - set(CHAPTER_KEYS), key=str):
        problems.append(f"{where}: unknown key '{key}'")
    cid, kind = raw.get("id"), raw.get("kind")
    status = raw.get("status", "da-fare")
    if not isinstance(cid, str) or not ID_RE.match(cid):
        problems.append(f"{where}.id: must match [a-z0-9][a-z0-9-]*, got {cid!r}")
    if kind not in KINDS:
        problems.append(f"{where}.kind: must be one of {list(KINDS)}, got {kind!r}")
    if status not in STATUSES:
        problems.append(f"{where}.status: must be one of {list(STATUSES)}, got {status!r}")
    title = raw.get("title")
    if not isinstance(title, str):
        problems.append(f"{where}.title: expected text, got {title!r}")
    return Chapter(id=cid, title=title, kind=kind, status=status,
                   source=_opt_str(raw.get("source"), f"{where}.source", problems),
                   notes=_opt_str(raw.get("notes"), f"{where}.notes", problems))


def parse_state(text: str) -> ProjectState:
    m = _HEADER.match(text)
    if m is None and not _HEADER_EMPTY.match(text):
        raise StateError("the file must start with a YAML header between '---' lines")
    header, body = (m.group(1), text[m.end():]) if m else ("", text[_HEADER_EMPTY.match(text).end():])
    try:
        data = yaml.safe_load(header)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        where = f"line {mark.line + 2}: " if mark else ""
        raise StateError(f"invalid YAML in the header, {where}"
                         f"{getattr(exc, 'problem', None) or exc}") from None
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise StateError("header: expected a mapping of fields")
    problems = []
    for key in sorted(set(data) - set(HEADER_KEYS), key=str):
        problems.append(f"unknown key '{key}'")
    if data.get("version", VERSION) != VERSION:
        problems.append(f"version: unsupported {data.get('version')!r} (expected {VERSION})")
    mode = data.get("mode")
    if mode not in MODES:
        problems.append(f"mode: must be one of {list(MODES)}, got {mode!r}")
    fmt = data.get("format")
    if fmt is not None and fmt not in FORMATS:
        problems.append(f"format: must be one of {list(FORMATS)} or null, got {fmt!r}")
    language = data.get("language", "it")
    if not isinstance(language, str):
        problems.append(f"language: expected text, got {language!r}")
    flags = {}
    for key in ("outline_approved", "title_page_approved"):
        flags[key] = data.get(key, False)
        if not isinstance(flags[key], bool):
            problems.append(f"{key}: expected true or false, got {flags[key]!r}")
    strings = {key: _opt_str(data.get(key), key, problems)
               for key in ("document_type", "profile", "draft", "output")}
    raw_chapters = data.get("chapters") or []
    chapters = []
    if not isinstance(raw_chapters, list):
        problems.append(f"chapters: expected a list, got {raw_chapters!r}")
        raw_chapters = []
    for i, raw in enumerate(raw_chapters):
        c = _chapter(raw, i, problems)
        if c is not None:
            chapters.append(c)
    seen = set()
    for c in chapters:
        if c.id in seen:
            problems.append(f"chapters: duplicate id '{c.id}'")
        seen.add(c.id)
    prints = data.get("fingerprints") or {}
    if not isinstance(prints, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in prints.items()):
        problems.append("fingerprints: expected a mapping of path to sha256 text")
        prints = {}
    if problems:
        raise StateError(problems)
    return ProjectState(mode=mode, format=fmt, language=language, chapters=chapters,
                        fingerprints=dict(prints), body=body, **flags, **strings)


def validate(state: ProjectState) -> None:
    """Raise StateError if state (changed in memory) would not load back."""
    parse_state(render_state(state))


def render_state(state: ProjectState) -> str:
    data = {"version": VERSION}
    for key in SCALAR_KEYS:
        data[key] = getattr(state, key)
    data["chapters"] = [asdict(c) for c in state.chapters]
    data["fingerprints"] = dict(state.fingerprints)
    header = yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=1000)
    return f"---\n{header}---\n{state.body}"


def load_state(work) -> ProjectState:
    path = state_path(work)
    try:
        text = path.read_bytes().decode("utf-8")
    except FileNotFoundError:
        raise StateError(f"no state file at {path}; create it with: state init") from None
    except (OSError, UnicodeDecodeError) as exc:
        raise StateError(f"cannot read {path}: {getattr(exc, 'strerror', None) or exc}") from None
    try:
        return parse_state(text)
    except StateError as exc:
        raise StateError([f"{path}: {p}" for p in exc.problems]) from None


def save_state(work, state: ProjectState) -> None:
    validate(state)
    path = state_path(work)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(render_state(state).encode("utf-8"))
    os.replace(tmp, path)


def relative_path(work, value) -> str:
    """value as a path relative to work (POSIX separators); StateError if it is outside."""
    work = Path(work)
    p = Path(value)
    try:
        if p.is_absolute():
            rel = p.resolve().relative_to(work.resolve())
        else:
            rel = Path(os.path.normpath(p))
            if rel.parts[:1] == ("..",):
                raise ValueError
    except ValueError:
        raise StateError(f"path is outside the work folder: {value}") from None
    return rel.as_posix()


# --- next step ------------------------------------------------------------------------------

def next_step(work, state: ProjectState) -> dict:
    def step(phase, why, chapter=None):
        return {"phase": phase, "chapter": chapter, "why": why}

    folder = Path(work) / STATE_DIR
    has_rules = (folder / "linee-guida.yaml").is_file()
    if state.mode == "solo-revisione":
        if not has_rules:
            return step("linee-guida", "guidelines file linee-guida.yaml is missing")
        return step("revisione", "review the existing document against the guidelines")
    if not (folder / "materiale.md").is_file():
        return step("materiale", "the material list materiale.md is missing")
    if not has_rules:
        return step("linee-guida", "guidelines file linee-guida.yaml is missing")
    if state.format is None:
        return step("formato", "the output format is not chosen")
    if not state.outline_approved:
        return step("struttura", "the outline is not approved")
    if not state.title_page_approved:
        return step("frontespizio", "the title page is not approved")
    order = {kind: i for i, kind in enumerate(KINDS)}
    order["corpo"] = -1
    chapters = sorted(state.chapters, key=lambda c: order[c.kind])  # stable: list order kept
    phases = {"da-fare": ("intervista", "the chapter has not been discussed yet"),
              "intervista-fatta": ("scrittura", "the interview is done, the chapter is unwritten"),
              "scritto": ("approvazione", "the chapter is written and awaits approval")}
    for c in chapters:
        if c.status in phases:
            phase, why = phases[c.status]
            return step(phase, why, c.id)
    if all(c.status == "revisionato" for c in chapters) and chapters:
        return step("fine", "every chapter is reviewed")
    return step("revisione", "all chapters are approved: review the whole document")


# --- fingerprints ---------------------------------------------------------------------------

_HASHED = {".tex", ".bib", ".docx"}


def fingerprint(path) -> str:
    path = Path(path)
    h = hashlib.sha256()
    if path.is_dir():
        files = sorted(p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in _HASHED)
        for p in files:
            h.update(p.relative_to(path).as_posix().encode("utf-8") + b"\0")
            h.update(p.read_bytes() + b"\0")
    else:
        h.update(path.read_bytes())
    return h.hexdigest()


def modified(work, state: ProjectState) -> dict:
    result = {}
    for rel, expected in state.fingerprints.items():
        p = Path(work) / rel
        result[rel] = "missing" if not p.exists() else (
            "unchanged" if fingerprint(p) == expected else "modified")
    return result


# --- command line ---------------------------------------------------------------------------

def add_arguments(parser):
    parser.add_argument("action", choices=["init", "show", "set", "outline", "chapter",
                                           "record", "modified"])
    parser.add_argument("work", help="work folder")
    parser.add_argument("rest", nargs="*", help="key=value (set), chapter id, or paths (record)")
    parser.add_argument("--mode", choices=MODES)
    parser.add_argument("--format", choices=FORMATS)
    parser.add_argument("--type", dest="document_type")
    parser.add_argument("--profile")
    parser.add_argument("--language")
    parser.add_argument("--draft")
    parser.add_argument("--output", dest="output_folder")
    parser.add_argument("--from", dest="from_file", help="outline.json (outline)")
    parser.add_argument("--status")
    parser.add_argument("--source")
    parser.add_argument("--notes")


def _scalar(key, text):
    if text == "null":
        return None
    if text in ("true", "false"):
        return text == "true"
    return text


def _usage(message):
    from . import cli
    raise cli.CliError(message)


def _outline(state, items):
    if not isinstance(items, list):
        _usage("outline: expected a JSON list of {id, title, kind}")
    known = {c.id: c for c in state.chapters}
    chapters, problems = [], []
    for i, item in enumerate(items):
        if not isinstance(item, dict) or set(item) - {"id", "title", "kind"}:
            problems.append(f"outline[{i}]: expected an object with id, title, kind")
            continue
        old = known.get(item.get("id"))
        chapters.append(Chapter(id=item.get("id"), title=item.get("title"),
                                kind=item.get("kind"),
                                status=old.status if old else "da-fare",
                                source=old.source if old else None,
                                notes=old.notes if old else None))
    if problems:
        raise StateError(problems)
    kept = {c.id for c in chapters}
    removed = [c.id for c in state.chapters if c.id not in kept]
    state.chapters = chapters
    return removed


def run(args) -> int:
    from . import cli

    work = Path(args.work)
    action = args.action
    try:
        if action == "init":
            if state_path(work).exists():
                raise cli.CliError(f"state file already exists: {state_path(work)}")
            if not work.is_dir():
                raise cli.CliError(f"not a folder: {work}")
            if not args.mode:
                raise cli.CliError("init needs --mode")
            state = ProjectState(mode=args.mode, document_type=args.document_type,
                                 profile=args.profile, format=args.format,
                                 language=args.language or "it")
            for key in PATH_KEYS:
                value = getattr(args, "output_folder" if key == "output" else key)
                if value:
                    setattr(state, key, relative_path(work, value))
            save_state(work, state)
            cli.emit({"state": str(state_path(work))}, args, text=f"created {state_path(work)}")
            return 0
        if not work.is_dir():
            raise cli.CliError(f"not a folder: {work}")
        state = load_state(work)
        if action == "show":
            data = asdict(state)
            data["next"] = next_step(work, state)
            n = data["next"]
            cli.emit(data, args, text=(
                f"mode: {state.mode}; format: {state.format}; chapters: {len(state.chapters)}\n"
                f"next: {n['phase']}" + (f" ({n['chapter']})" if n["chapter"] else "")
                + f" - {n['why']}"))
            return 0
        if action == "modified":
            result = modified(work, state)
            cli.emit(result, args, text="\n".join(f"{v}: {k}" for k, v in result.items())
                     or "no recorded files")
            return 0
        if action == "set":
            if not args.rest:
                raise cli.CliError("set needs key=value arguments")
            for pair in args.rest:
                key, sep, value = pair.partition("=")
                if not sep or key not in SCALAR_KEYS:
                    raise cli.CliError(
                        f"cannot set '{key}': use one of {', '.join(SCALAR_KEYS)} as key=value")
                value = _scalar(key, value)
                if key in PATH_KEYS and isinstance(value, str):
                    value = relative_path(work, value)
                setattr(state, key, value)
            save_state(work, state)
            cli.emit({"updated": [p.partition("=")[0] for p in args.rest]}, args,
                     text="updated " + ", ".join(p.partition("=")[0] for p in args.rest))
            return 0
        if action == "outline":
            if not args.from_file:
                raise cli.CliError("outline needs --from outline.json")
            try:
                items = json.loads(Path(args.from_file).read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise cli.CliError(f"cannot read {args.from_file}: {exc}") from None
            removed = _outline(state, items)
            save_state(work, state)
            cli.emit({"chapters": [c.id for c in state.chapters], "removed": removed}, args,
                     text=f"{len(state.chapters)} chapter(s); removed: {removed or 'none'}")
            return 0
        if action == "chapter":
            if len(args.rest) != 1:
                raise cli.CliError("chapter needs exactly one chapter id")
            chapter = next((c for c in state.chapters if c.id == args.rest[0]), None)
            if chapter is None:
                raise cli.CliError(f"unknown chapter id '{args.rest[0]}'")
            if args.status:
                chapter.status = args.status
            if args.source:
                chapter.source = relative_path(work, args.source)
            if args.notes:
                chapter.notes = relative_path(work, args.notes)
            save_state(work, state)
            cli.emit(asdict(chapter), args, text=f"{chapter.id}: {chapter.status}")
            return 0
        # record
        if not args.rest:
            raise cli.CliError("record needs one or more paths")
        for value in args.rest:
            rel = relative_path(work, value)
            if not (work / rel).exists():
                raise cli.CliError(f"no such file or folder: {value}")
            state.fingerprints[rel] = fingerprint(work / rel)
        save_state(work, state)
        cli.emit({"recorded": sorted(state.fingerprints)}, args,
                 text="recorded " + ", ".join(args.rest))
        return 0
    except StateError as exc:
        for problem in exc.problems:
            print(f"error: {problem}", file=sys.stderr)
        return 2
