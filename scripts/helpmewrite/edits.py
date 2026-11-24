"""Edit lists written by the reviewer agents (EditSet JSON) and the `track` command.

An edit addresses a paragraph (docx/pdf: `paragraph`, the id from extract) or a source
line (tex: `file` and `line`), finds `find` there and replaces it (`replace`, "" deletes)
and/or comments on it (`comment`).
"""
import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

AUTHOR = "help-me-write"
REVIEWERS = ("revisore", "bibliografia")
_EDIT_KEYS = ("paragraph", "file", "line", "find", "replace", "comment", "reason", "by")
# characters XML (hence a .docx) cannot hold
_NOT_XML = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]")


@dataclass
class Edit:
    paragraph: int | None
    file: str | None
    line: int | None
    find: str
    replace: str | None
    comment: str | None
    reason: str
    by: str


@dataclass
class EditSet:
    author: str
    edits: list[Edit] = field(default_factory=list)


class EditsError(Exception):
    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__("; ".join(self.problems))


def edit_to_dict(edit: Edit) -> dict:
    """JSON form of an edit; absent fields (None) are left out."""
    return {k: v for k, v in asdict(edit).items() if v is not None}


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _parse_edit(raw, where, problems):
    if not isinstance(raw, dict):
        problems.append(f"{where}: expected an object, got {type(raw).__name__}")
        return None
    start = len(problems)
    for key in sorted(set(raw) - set(_EDIT_KEYS), key=str):
        problems.append(f"{where}: unknown key '{key}'")
    paragraph, file, line = raw.get("paragraph"), raw.get("file"), raw.get("line")
    if paragraph is not None and not (_is_int(paragraph) and paragraph >= 0):
        problems.append(f"{where}: paragraph must be an integer >= 0, got {paragraph!r}")
    if file is not None and not (isinstance(file, str) and file):
        problems.append(f"{where}: file must be a non-empty string, got {file!r}")
    if line is not None and not (_is_int(line) and line >= 1):
        problems.append(f"{where}: line must be an integer >= 1, got {line!r}")
    if paragraph is None and (file is None or line is None):
        problems.append(f"{where}: needs 'paragraph' (docx, pdf) or both 'file' and 'line' (tex)")
    find = raw.get("find")
    if not (isinstance(find, str) and find):
        problems.append(f"{where}: find must be a non-empty string, got {find!r}")
    replace, comment = raw.get("replace"), raw.get("comment")
    if replace is not None and not isinstance(replace, str):
        problems.append(f"{where}: replace must be a string (\"\" deletes), got {replace!r}")
    if comment is not None and not (isinstance(comment, str) and comment.strip()):
        problems.append(f"{where}: comment must be a non-empty string, got {comment!r}")
    if replace is None and comment is None:
        problems.append(f"{where}: needs 'replace' or 'comment' (or both)")
    for name, value in (("find", find), ("replace", replace), ("comment", comment)):
        if isinstance(value, str) and _NOT_XML.search(value):
            problems.append(f"{where}: {name} contains control characters a document cannot hold")
    reason = raw.get("reason")
    if not (isinstance(reason, str) and reason.strip()):
        problems.append(f"{where}: reason must be a non-empty string, got {reason!r}")
    by = raw.get("by")
    if by not in REVIEWERS:
        problems.append(f"{where}: by must be one of {list(REVIEWERS)}, got {by!r}")
    if len(problems) > start:
        return None
    return Edit(paragraph, file, line, find, replace, comment, reason, by)


def parse_edits(data) -> EditSet:
    """Validate the JSON form of an EditSet; EditsError lists every problem."""
    if not isinstance(data, dict):
        raise EditsError(["top level: expected an object with 'author' and 'edits'"])
    problems = []
    for key in sorted(set(data) - {"author", "edits"}, key=str):
        problems.append(f"unknown key '{key}'")
    author = data.get("author", AUTHOR)
    if not (isinstance(author, str) and author.strip()) or _NOT_XML.search(author):
        problems.append(f"author must be a non-empty string, got {author!r}")
    raw_edits = data.get("edits")
    if not isinstance(raw_edits, list):
        problems.append("edits: expected a list of edits")
        raw_edits = []
    edits = [_parse_edit(raw, f"edits[{i}]", problems) for i, raw in enumerate(raw_edits)]
    if problems:
        raise EditsError(problems)
    return EditSet(author, edits)


def load_edits(path) -> EditSet:
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise EditsError([f"cannot read {path}: {exc.strerror or exc}"])
    except UnicodeDecodeError:
        raise EditsError([f"{path} is not UTF-8 text"])
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise EditsError([f"{path} is not valid JSON: {exc}"])
    return parse_edits(data)


def dump_edits(edit_set: EditSet, path) -> None:
    data = {"author": edit_set.author, "edits": [edit_to_dict(e) for e in edit_set.edits]}
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def locate(text: str, find: str):
    """(start, end) of the only occurrence of find in text, else "not found"/"ambiguous"."""
    start = text.find(find)
    if start < 0:
        return "not found"
    if text.find(find, start + 1) >= 0:  # overlapping repeats count too
        return "ambiguous"
    return start, start + len(find)


def location(edit: Edit):
    """Where an edit applies: the paragraph id, or (file, line) for LaTeX."""
    return edit.paragraph if edit.paragraph is not None else (edit.file, edit.line)


def _where(key) -> str:
    return f"paragraph {key}" if isinstance(key, int) else f"{key[0]}:{key[1]}"


def merge_edits(*sets: EditSet, texts=None) -> tuple[EditSet, list[dict]]:
    """Concatenate edit sets, dropping every edit whose find overlaps an earlier one.

    texts maps a location (see location()) to the text the finds are searched in; there
    two edits conflict when their character spans overlap, and an edit whose find cannot
    be located is kept (applying it reports "not found"/"ambiguous"). Without the text
    of a location, two finds there conflict only if one contains the other.
    Returns the merged set and the conflicts as {"edit", "reason"}, first edit kept.
    """
    author = sets[0].author if sets else AUTHOR
    kept, conflicts = [], []
    taken = {}  # location -> [(span or None, edit)]
    for edit_set in sets:
        for edit in edit_set.edits:
            key = location(edit)
            span = None
            if texts is not None and key in texts:
                span = locate(texts[key], edit.find)
                if isinstance(span, str):
                    kept.append(edit)
                    continue
            other = next((o for o_span, o in taken.get(key, [])
                          if _overlap(span, edit, o_span, o)), None)
            if other is None:
                kept.append(edit)
                taken.setdefault(key, []).append((span, edit))
            elif (other.find, other.replace, other.comment) == (edit.find, edit.replace,
                                                                edit.comment):
                conflicts.append({"edit": edit_to_dict(edit),
                                  "reason": f"duplicate of an earlier edit in {_where(key)}"})
            else:
                conflicts.append({"edit": edit_to_dict(edit),
                                  "reason": f"overlaps an earlier edit in {_where(key)} "
                                            f"(find {other.find!r}, by {other.by})"})
    return EditSet(author, kept), conflicts


def _overlap(span, edit, other_span, other) -> bool:
    if span is not None and other_span is not None:
        return span[0] < other_span[1] and other_span[0] < span[1]
    return edit.find in other.find or other.find in edit.find


# --- the `track` command ---------------------------------------------------------------


def add_track_arguments(parser):
    parser.add_argument("document", help="document to correct (.docx, or the main .tex); never modified")
    parser.add_argument("--edits", action="append", required=True,
                        help="EditSet JSON; repeat to merge the edits of several reviewers")
    parser.add_argument("-o", "--output", required=True, help="corrected copy to write (for .tex: a new project folder)")


def _error(message) -> int:
    print(f"error: {message}", file=sys.stderr)
    return 2


def run_track(args) -> int:
    from . import cli

    source, output = Path(args.document), Path(args.output)
    if not source.is_file():
        return _error(f"file not found: {source}")
    if cli.refuses_overwrite(source, args):
        return 2
    if any(Path(e).resolve() == output.resolve() for e in args.edits):
        return _error(f"output would overwrite an edits file: {output}")
    suffix = source.suffix.lower()
    if suffix not in (".docx", ".tex"):
        return _error(f"unsupported format '{source.suffix}' for track (use .docx or .tex)")
    sets, invalid = [], False
    for path in args.edits:
        try:
            sets.append(load_edits(path))
        except EditsError as exc:
            invalid = True
            print(f"error: invalid edits in {path}:", file=sys.stderr)
            for problem in exc.problems:
                print(f"- {problem}", file=sys.stderr)
    if invalid:
        return 2

    from . import track_docx, track_tex
    from .extract import extract_tex, iter_body_paragraphs, visible_text

    try:
        if suffix == ".tex":
            texts = {(p["file"], p["line"]): p["text"] for p in extract_tex(source)}
            merged, conflicts = merge_edits(*sets, texts=texts)
            result = track_tex.apply_edits_tex(source, merged, output)
        else:
            import docx

            paragraphs = iter_body_paragraphs(docx.Document(str(source)))
            texts = {i: visible_text(p) for i, p in enumerate(paragraphs)}
            merged, conflicts = merge_edits(*sets, texts=texts)
            result = track_docx.apply_edits_docx(source, merged, output)
    except EditsError as exc:
        return _error("; ".join(exc.problems))
    except Exception as exc:  # unreadable/not a docx, unwritable destination
        return _error(f"cannot apply edits to {source.name}: {exc!r}")
    failed = [dict(f, edit=edit_to_dict(merged.edits[f["index"]])) for f in result.failed]
    data = {"applied": result.applied, "failed": failed, "conflicts": conflicts}
    if result.notes:
        data["notes"] = result.notes
    lines = [f"wrote {output}: {len(result.applied)} applied, {len(failed)} failed, "
             f"{len(conflicts)} conflicts"]
    for f in failed:
        lines.append(f"- failed [{f['index']}] {_where(location(merged.edits[f['index']]))} "
                     f"{f['edit']['find']!r}: {f['reason']}")
    for note in result.notes:
        lines.append(f"- note: {note}")
    for c in conflicts:
        lines.append(f"- conflict {c['edit']['find']!r}: {c['reason']}")
    cli.emit(data, argparse.Namespace(json=args.json, output=None), text="\n".join(lines))
    return 0 if not failed and not conflicts else 1
